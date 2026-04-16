"""
VendaFlow AI — Evolution API Webhook Routes
Recebe mensagens do WhatsApp e aciona o agente de vendas IA.
Baseado na arquitetura do EduFlow, adaptado para vendas.
"""
import json
import uuid
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models import Contact, Message, Channel, Tenant, AIConfig
from app.agents.sales_agent import process_sales_message
from app.evolution_client import send_text, send_image

router = APIRouter(prefix="/evolution", tags=["WhatsApp Evolution"])

SP_TZ = timezone(timedelta(hours=-3))


def _extract_message(data: dict) -> tuple[str, str, str]:
    """Extrai texto, tipo e media_url da mensagem do Evolution."""
    msg_type = data.get("messageType", "conversation")
    text = ""
    media_url = ""
    
    message = data.get("message", {})
    
    if msg_type == "conversation":
        text = message.get("conversation", "") or data.get("body", "")
    elif msg_type == "extendedTextMessage":
        text = message.get("extendedTextMessage", {}).get("text", "")
    elif msg_type in ("imageMessage", "videoMessage", "documentMessage"):
        caption = message.get(msg_type, {}).get("caption", "")
        text = caption or f"[{msg_type.replace('Message', '')}]"
        media_url = message.get(msg_type, {}).get("url", "")
    elif msg_type in ("audioMessage", "pttMessage"):
        text = "[áudio recebido]"
    elif msg_type == "listResponseMessage":
        text = message.get("listResponseMessage", {}).get("title", "")
    elif msg_type == "buttonsResponseMessage":
        text = message.get("buttonsResponseMessage", {}).get("selectedDisplayText", "")
    else:
        text = data.get("body", "") or message.get("conversation", "") or ""
    
    return text.strip(), msg_type, media_url


@router.post("/webhook/{instance_name}")
async def evolution_webhook(
    instance_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook principal do Evolution API.
    Recebe todas as mensagens de uma instância WhatsApp.
    
    URL para configurar no Evolution:
    POST https://seudominio.com/evolution/webhook/{instance_name}
    """
    try:
        payload = await request.json()
    except Exception:
        return {"status": "invalid_json"}
    
    event = payload.get("event", "")
    
    # Só processar mensagens recebidas
    if event != "messages.upsert":
        return {"status": "ignored", "event": event}
    
    data = payload.get("data", {})
    key = data.get("key", {})
    
    # Ignorar mensagens enviadas por nós
    if key.get("fromMe", False):
        return {"status": "ignored", "reason": "fromMe"}
    
    # Ignorar status updates
    if data.get("messageType") == "protocolMessage":
        return {"status": "ignored", "reason": "protocol"}
    
    # Extrair dados
    wa_id = key.get("remoteJid", "").replace("@s.whatsapp.net", "").replace("@g.us", "")
    if not wa_id or "@g.us" in key.get("remoteJid", ""):
        return {"status": "ignored", "reason": "group_or_invalid"}
    
    push_name = data.get("pushName", "Cliente")
    message_id = key.get("id", f"evo_{uuid.uuid4().hex[:16]}")
    text, msg_type, media_url = _extract_message(data)
    
    if not text:
        return {"status": "ignored", "reason": "empty_message"}
    
    # ── Buscar canal ──────────────────────────────────────────────────────
    channel_result = await db.execute(
        select(Channel).where(Channel.instance_name == instance_name)
    )
    channel = channel_result.scalar_one_or_none()
    
    if not channel:
        print(f"⚠️ Canal não encontrado para instância: {instance_name}")
        return {"status": "error", "reason": "channel_not_found"}
    
    tenant_id = channel.tenant_id
    
    # ── Buscar/criar contato ──────────────────────────────────────────────
    contact_result = await db.execute(
        select(Contact).where(
            Contact.wa_id == wa_id,
            Contact.tenant_id == tenant_id,
        )
    )
    contact = contact_result.scalar_one_or_none()
    
    if not contact:
        contact = Contact(
            tenant_id=tenant_id,
            wa_id=wa_id,
            name=push_name,
            channel_id=channel.id,
            lead_status="novo",
            ai_active=True,
        )
        db.add(contact)
        await db.flush()
    
    # Atualizar último contato
    contact.last_inbound_at = datetime.now(SP_TZ).replace(tzinfo=None)
    if push_name and push_name != "Cliente" and (not contact.name or contact.name == "Cliente"):
        contact.name = push_name
    
    # ── Salvar mensagem recebida ──────────────────────────────────────────
    # Verificar duplicata
    existing_msg = await db.execute(
        select(Message).where(Message.wa_message_id == message_id)
    )
    if existing_msg.scalar_one_or_none():
        return {"status": "duplicate"}
    
    inbound_msg = Message(
        tenant_id=tenant_id,
        wa_message_id=message_id,
        contact_wa_id=wa_id,
        channel_id=channel.id,
        direction="inbound",
        message_type=msg_type,
        content=text,
        media_url=media_url or None,
        timestamp=datetime.now(SP_TZ).replace(tzinfo=None),
        status="received",
        sent_by_ai=False,
        sender_name=push_name,
    )
    db.add(inbound_msg)
    await db.commit()
    
    # ── Verificar se IA está ativa ────────────────────────────────────────
    if not contact.ai_active:
        return {"status": "ai_disabled_for_contact"}
    
    ai_config_result = await db.execute(
        select(AIConfig).where(AIConfig.channel_id == channel.id)
    )
    ai_config = ai_config_result.scalar_one_or_none()
    
    if not ai_config or not ai_config.is_enabled:
        return {"status": "ai_disabled_for_channel"}
    
    # ── Processar com agente de vendas ────────────────────────────────────
    print(f"🛒 [{instance_name}] {push_name} ({wa_id}): {text[:80]}")
    
    result = await process_sales_message(
        wa_id=wa_id,
        user_message=text,
        contact_name=push_name,
        instance_name=instance_name,
        channel_id=channel.id,
        db=db,
        tenant_id=tenant_id,
        input_message_type=msg_type,
    )
    
    ai_message = result.get("message", "")
    payment_url = result.get("payment_url")
    image_url_to_send = result.get("image_url")
    
    if not ai_message:
        return {"status": "no_response"}
    
    # ── Enviar imagem do produto (se disponível) ──────────────────────────
    if image_url_to_send:
        try:
            await send_image(instance_name, wa_id, image_url_to_send, "")
        except Exception as e:
            print(f"⚠️ Erro ao enviar imagem: {e}")
    
    # ── Enviar resposta de texto ──────────────────────────────────────────
    await send_text(instance_name, wa_id, ai_message)
    
    # Salvar mensagem da IA
    ai_msg_record = Message(
        tenant_id=tenant_id,
        wa_message_id=f"ai_{uuid.uuid4().hex[:16]}",
        contact_wa_id=wa_id,
        channel_id=channel.id,
        direction="outbound",
        message_type="text",
        content=ai_message,
        timestamp=datetime.now(SP_TZ).replace(tzinfo=None),
        status="sent",
        sent_by_ai=True,
        ai_action=result.get("action"),
    )
    db.add(ai_msg_record)
    
    # ── Enviar link de pagamento separado (destaque) ──────────────────────
    if payment_url:
        link_message = f"💳 *Link de Pagamento*\n\nFinalize sua compra pelo link abaixo:\n{payment_url}\n\n✅ Pagamento seguro via Pix, cartão ou boleto."
        await send_text(instance_name, wa_id, link_message)
        
        link_msg_record = Message(
            tenant_id=tenant_id,
            wa_message_id=f"ai_link_{uuid.uuid4().hex[:16]}",
            contact_wa_id=wa_id,
            channel_id=channel.id,
            direction="outbound",
            message_type="text",
            content=link_message,
            timestamp=datetime.now(SP_TZ).replace(tzinfo=None),
            status="sent",
            sent_by_ai=True,
            ai_action="payment_link_sent",
        )
        db.add(link_msg_record)
    
    await db.commit()
    
    print(f"🤖 [{instance_name}] → {wa_id}: {ai_message[:80]}... | tools: {result.get('tools_used', [])}")
    
    return {
        "status": "processed",
        "action": result.get("action"),
        "tools_used": result.get("tools_used", []),
        "payment_link_sent": bool(payment_url),
    }
