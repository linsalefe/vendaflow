"""
VendaFlow AI — Sales Agent (Core)
Agente de IA que conversa pelo WhatsApp e VENDE.
Usa function calling do GPT para buscar produtos, montar carrinho e gerar link de pagamento.

Diferença do EduFlow: aqui a IA não qualifica leads, ela FECHA vendas.
"""
import os
import json
import uuid
import re
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from app.models import (
    Contact, Message, AIConfig, Channel, Tenant, TokenUsage,
    SalesConversation, Product
)
from app.agents.tools import SALES_AGENT_TOOLS
from app.agents.executor import execute_tool

SP_TZ = timezone(timedelta(hours=-3))
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT BASE (usado se o tenant não configurar um customizado)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_SALES_PROMPT = """Você é uma vendedora virtual especializada chamada Lia.
Seu objetivo é VENDER os produtos disponíveis no catálogo via WhatsApp.

PERSONALIDADE:
- Simpática, direta e persuasiva (sem ser invasiva)
- Usa emojis com moderação (1-2 por mensagem)
- Fala como uma vendedora experiente: conhece os produtos, sabe recomendar
- Sempre responde em português brasileiro

FLUXO DE VENDA (siga nesta ordem):
1. SAUDAÇÃO: Cumprimente e pergunte como pode ajudar
2. DESCOBERTA: Entenda o que o cliente procura (use search_products)
3. APRESENTAÇÃO: Mostre os produtos relevantes com preços e benefícios
4. OBJEÇÕES: Responda dúvidas e quebre objeções com os argumentos do produto
5. CARRINHO: Quando o cliente demonstrar interesse, adicione ao carrinho (add_to_cart)
6. UPSELL: Sugira produtos complementares (get_upsell_suggestions)
7. CHECKOUT: Confirme o carrinho e gere o link de pagamento (create_order_and_payment_link)
8. PÓS-VENDA: Confirme que o link foi enviado e agradeça

REGRAS CRÍTICAS:
- SEMPRE use as tools para buscar produtos e preços reais. NUNCA invente preços.
- Quando o cliente confirmar que quer comprar, adicione ao carrinho E gere o link de pagamento.
- Para produtos com variantes (tamanho/cor), PERGUNTE antes de adicionar.
- Se o cliente pedir atacado, verifique a quantidade mínima e aplique o preço de atacado.
- Se o cliente enviar um cupom, use apply_coupon para validar.
- Sempre mova o pipeline conforme a conversa avança (move_pipeline).
- Colete dados do cliente (nome, email) quando possível (collect_customer_data).
- Se o produto estiver sem estoque, avise e sugira alternativas.
- NÃO gere link de pagamento sem itens no carrinho.
- Envie imagens dos produtos quando disponíveis.

FORMATO DAS MENSAGENS:
- Máximo 3-4 parágrafos curtos por mensagem
- Use *negrito* para preços e nomes de produtos
- Use listas simples quando mostrar múltiplos produtos
- Nunca envie mensagens muito longas (cliente está no celular)
"""


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def get_ai_config(channel_id: int, db: AsyncSession) -> AIConfig | None:
    result = await db.execute(
        select(AIConfig).where(AIConfig.channel_id == channel_id)
    )
    return result.scalar_one_or_none()


async def get_conversation_history(wa_id: str, db: AsyncSession, limit: int = 25) -> list:
    """Busca últimas mensagens para contexto."""
    result = await db.execute(
        select(Message)
        .where(Message.contact_wa_id == wa_id)
        .order_by(Message.timestamp.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    messages.reverse()

    history = []
    for msg in messages:
        if msg.direction == "outbound" and msg.sent_by_ai:
            role = "assistant"
        elif msg.direction == "inbound":
            role = "user"
        else:
            continue
        if msg.content:
            history.append({"role": role, "content": msg.content})

    return history


async def get_or_create_sales_conversation(
    wa_id: str, tenant_id: int, channel_id: int, db: AsyncSession
) -> SalesConversation:
    """Busca ou cria uma sessão de venda ativa."""
    result = await db.execute(
        select(SalesConversation).where(
            SalesConversation.contact_wa_id == wa_id,
            SalesConversation.tenant_id == tenant_id,
            SalesConversation.stage.notin_(["paid", "delivered", "cancelled"]),
        ).order_by(SalesConversation.created_at.desc()).limit(1)
    )
    conv = result.scalar_one_or_none()

    if not conv:
        conv = SalesConversation(
            tenant_id=tenant_id,
            contact_wa_id=wa_id,
            channel_id=channel_id,
            stage="greeting",
        )
        db.add(conv)
        await db.flush()

    return conv


async def build_catalog_context(tenant_id: int, db: AsyncSession) -> str:
    """Monta uma lista resumida dos produtos para o contexto da IA."""
    result = await db.execute(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.is_active == True,
        ).order_by(Product.is_featured.desc(), Product.sort_order).limit(20)
    )
    products = result.scalars().all()

    if not products:
        return "\n📦 CATÁLOGO: Nenhum produto cadastrado ainda."

    lines = ["\n📦 CATÁLOGO RESUMIDO (use search_products para detalhes):"]
    for p in products:
        stock_info = f"({p.stock_quantity} em estoque)" if p.track_stock else ""
        wholesale = f" | Atacado: R${p.wholesale_price}/{p.wholesale_min_qty}+ un" if p.wholesale_price else ""
        featured = " ⭐" if p.is_featured else ""
        lines.append(
            f"- [ID:{p.id}] {p.name}{featured}: R${p.price}{wholesale} {stock_info}"
        )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS MESSAGE — CORE DO AGENTE
# ─────────────────────────────────────────────────────────────────────────────

async def process_sales_message(
    wa_id: str,
    user_message: str,
    contact_name: str,
    instance_name: str,
    channel_id: int,
    db: AsyncSession,
    tenant_id: int = None,
    input_message_type: str = "text",
) -> dict:
    """
    Processa mensagem do cliente e gera resposta de venda com function calling.
    
    Returns:
        {
            "message": str,            # texto para enviar ao cliente
            "action": str,             # stage atual da venda
            "payment_url": str | None, # link de pagamento (se gerado)
            "image_url": str | None,   # imagem do produto (se relevante)
            "tools_used": list,        # tools que foram chamadas
        }
    """

    # ── Buscar tenant ─────────────────────────────────────────────────────
    tenant = None
    if tenant_id:
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()

        # Bloquear se sem créditos
        if tenant and tenant.credits_balance <= 0:
            print(f"🚫 Tenant {tenant_id} sem créditos. IA bloqueada.")
            return {"message": "", "action": "blocked", "payment_url": None, "image_url": None, "tools_used": []}

    # ── Buscar contato ────────────────────────────────────────────────────
    contact_result = await db.execute(
        select(Contact).where(Contact.wa_id == wa_id, Contact.tenant_id == tenant_id)
    )
    contact = contact_result.scalar_one_or_none()

    # ── Config da IA ──────────────────────────────────────────────────────
    ai_config = await get_ai_config(channel_id, db)
    
    system_prompt = DEFAULT_SALES_PROMPT
    if ai_config and ai_config.system_prompt:
        system_prompt = ai_config.system_prompt
    elif tenant and tenant.ai_sales_prompt:
        system_prompt = tenant.ai_sales_prompt

    model = (ai_config.model if ai_config and ai_config.model else
             tenant.ai_model if tenant else "gpt-4.1")
    temperature = float(ai_config.temperature if ai_config and ai_config.temperature else
                        tenant.ai_temperature if tenant else 0.4)
    max_tokens = ai_config.max_tokens if ai_config else 600

    # ── Contexto do catálogo ──────────────────────────────────────────────
    catalog_ctx = await build_catalog_context(tenant_id, db)

    # ── Sales conversation ────────────────────────────────────────────────
    sales_conv = await get_or_create_sales_conversation(wa_id, tenant_id, channel_id, db)
    sales_conv.messages_count = (sales_conv.messages_count or 0) + 1

    # ── Histórico ─────────────────────────────────────────────────────────
    history = await get_conversation_history(wa_id, db)

    # ── Contexto do lead ──────────────────────────────────────────────────
    lead_info = f"\nDados do cliente: Nome={contact_name}"
    if contact:
        if contact.email:
            lead_info += f", Email={contact.email}"
        if contact.is_wholesale:
            lead_info += ", Tipo=ATACADO"
        if contact.total_orders and contact.total_orders > 0:
            lead_info += f", Pedidos anteriores={contact.total_orders}, Total gasto=R${contact.total_spent}"
        if contact.notes:
            try:
                notes = json.loads(contact.notes)
                if notes:
                    lead_info += f", Preferências={json.dumps(notes, ensure_ascii=False)}"
            except (json.JSONDecodeError, TypeError):
                pass

    lead_info += f"\nEstágio atual da venda: {sales_conv.stage}"
    if sales_conv.interests:
        lead_info += f"\nInteresses detectados: {json.dumps(sales_conv.interests, ensure_ascii=False)}"
    if sales_conv.objections:
        lead_info += f"\nObjeções levantadas: {json.dumps(sales_conv.objections, ensure_ascii=False)}"

    # ── Montar mensagens ──────────────────────────────────────────────────
    messages = [
        {"role": "system", "content": system_prompt + catalog_ctx + lead_info},
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # ── Chamar GPT com function calling ──────────────────────────────────
    tools_used = []
    payment_url = None
    image_url = None
    max_tool_rounds = 5  # máximo de rounds de function calling

    try:
        for round_num in range(max_tool_rounds):
            api_params = {
                "model": model,
                "messages": messages,
                "tools": SALES_AGENT_TOOLS,
                "tool_choice": "auto",
                "max_completion_tokens": max_tokens,
            }
            if not model.startswith("gpt-5") and not model.startswith("o"):
                api_params["temperature"] = temperature

            response = await client.chat.completions.create(**api_params)
            choice = response.choices[0]

            # Salvar uso de tokens
            try:
                usage = response.usage
                if usage and tenant_id:
                    db.add(TokenUsage(
                        tenant_id=tenant_id,
                        source="sales_ai",
                        model=response.model,
                        prompt_tokens=usage.prompt_tokens or 0,
                        completion_tokens=usage.completion_tokens or 0,
                        total_tokens=usage.total_tokens or 0,
                    ))
                    # Debitar crédito
                    if tenant:
                        tenant.credits_balance = max(0, (tenant.credits_balance or 0) - 1)
                        tenant.credits_used = (tenant.credits_used or 0) + 1
            except Exception as e:
                print(f"⚠️ Erro ao salvar token usage: {e}")

            # Se o modelo terminou (sem tool calls) → resposta final
            if choice.finish_reason == "stop" or not choice.message.tool_calls:
                break

            # Processar tool calls
            assistant_msg = choice.message
            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in assistant_msg.tool_calls
                ]
            })

            for tc in assistant_msg.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                print(f"🔧 Tool call: {fn_name}({json.dumps(fn_args, ensure_ascii=False)})")
                tools_used.append(fn_name)

                # Executar tool
                tool_result = await execute_tool(
                    tool_name=fn_name,
                    args=fn_args,
                    wa_id=wa_id,
                    tenant_id=tenant_id,
                    db=db,
                )

                # Capturar dados relevantes do resultado
                try:
                    result_data = json.loads(tool_result)
                    if result_data.get("payment_url"):
                        payment_url = result_data["payment_url"]
                    if result_data.get("image_url"):
                        image_url = result_data["image_url"]
                    # Primeira imagem de produto encontrado
                    if not image_url and result_data.get("products"):
                        for p in result_data["products"]:
                            if p.get("image_url"):
                                image_url = p["image_url"]
                                break
                except (json.JSONDecodeError, TypeError):
                    pass

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })

        # ── Extrair resposta final ────────────────────────────────────────
        ai_message = (response.choices[0].message.content or "").strip()

        # Fallback: se resposta vazia com gpt-5, retry com gpt-4o-mini
        if not ai_message and model.startswith("gpt-5"):
            print(f"⚠️ GPT-5 retornou vazio, retry com gpt-4o-mini...")
            fallback_response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            ai_message = (fallback_response.choices[0].message.content or "").strip()

        # ── Detectar stage da venda pelo conteúdo ─────────────────────────
        if "create_order_and_payment_link" in tools_used:
            sales_conv.stage = "link_sent"
        elif "add_to_cart" in tools_used:
            sales_conv.stage = "cart_built"
        elif "search_products" in tools_used or "get_product_details" in tools_used:
            if sales_conv.stage == "greeting":
                sales_conv.stage = "browsing"

        # ── Detectar interesses e objeções ────────────────────────────────
        msg_lower = user_message.lower()
        interest_keywords = ["quero", "tem", "quanto", "preço", "comprar", "kit", "camisa", "blusa"]
        objection_keywords = ["caro", "barato", "desconto", "frete", "demora", "não sei"]

        for kw in interest_keywords:
            if kw in msg_lower and kw not in (sales_conv.interests or []):
                if not sales_conv.interests:
                    sales_conv.interests = []
                sales_conv.interests.append(kw)

        for kw in objection_keywords:
            if kw in msg_lower and kw not in (sales_conv.objections or []):
                if not sales_conv.objections:
                    sales_conv.objections = []
                sales_conv.objections.append(kw)

        await db.commit()

        return {
            "message": ai_message,
            "action": sales_conv.stage,
            "payment_url": payment_url,
            "image_url": image_url,
            "tools_used": tools_used,
        }

    except Exception as e:
        print(f"❌ Erro agente de vendas: {e}")
        import traceback
        traceback.print_exc()
        return {
            "message": "",
            "action": "error",
            "payment_url": None,
            "image_url": None,
            "tools_used": tools_used,
        }
