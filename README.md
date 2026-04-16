# VendaFlow AI

## CRM de Vendas com IA que vai até o Checkout

**Stack:** FastAPI + Next.js + PostgreSQL + OpenAI + Evolution API  
**Baseado na arquitetura:** EduFlow Hub (multi-tenant, WhatsApp, AI agents)

---

## O que é

VendaFlow AI é um CRM de vendas onde a **IA é a vendedora**. Ela conversa com o cliente pelo WhatsApp, mostra produtos, monta o carrinho, aplica cupom e gera link de pagamento — tudo automaticamente.

### Diferenciais vs EduFlow
| EduFlow | VendaFlow |
|---------|-----------|
| IA qualifica leads | IA **fecha vendas** |
| Agenda reuniões | Gera **link de pagamento** |
| Pipeline educacional | Pipeline de **e-commerce** |
| Sem catálogo | **Catálogo completo** com variantes |
| Sem pagamento | **Stripe + Hotmart + Kiwify** |

---

## Arquitetura

```
┌────────────────────────────────────────────────────────────────────┐
│                        CLIENTE (WhatsApp)                         │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ mensagem
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     EVOLUTION API (WhatsApp)                         │
│              POST /evolution/webhook/{instance_name}                  │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      VENDAFLOW AI (FastAPI)                          │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                   SALES AGENT (GPT + Tools)                  │    │
│  │                                                               │    │
│  │  1. Recebe mensagem do cliente                                │    │
│  │  2. Consulta histórico + catálogo + contexto                  │    │
│  │  3. GPT decide qual tool chamar:                              │    │
│  │     ┌─────────────────────────────────────────────┐           │    │
│  │     │  search_products      → buscar catálogo     │           │    │
│  │     │  get_product_details  → detalhes + imagens  │           │    │
│  │     │  check_stock          → verificar estoque   │           │    │
│  │     │  add_to_cart          → montar carrinho     │           │    │
│  │     │  view_cart            → resumo do carrinho  │           │    │
│  │     │  apply_coupon         → validar cupom       │           │    │
│  │     │  create_order_and_payment_link → CHECKOUT   │           │    │
│  │     │  collect_customer_data → salvar dados CRM   │           │    │
│  │     │  move_pipeline        → atualizar pipeline  │           │    │
│  │     │  get_upsell_suggestions → cross-sell        │           │    │
│  │     └─────────────────────────────────────────────┘           │    │
│  │  4. Executa tool → retorna resultado → GPT monta resposta    │    │
│  │  5. Envia resposta + imagem + link de pagamento              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  GATEWAY FACTORY                              │    │
│  │                                                               │    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────┐                │    │
│  │  │  STRIPE   │  │  HOTMART  │  │  KIWIFY   │                │    │
│  │  │           │  │           │  │           │                │    │
│  │  │ Checkout  │  │ Checkout  │  │ Checkout  │                │    │
│  │  │ Session   │  │ nativo    │  │ nativo    │                │    │
│  │  │ Pix/Card  │  │ c/ params │  │ c/ params │                │    │
│  │  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘                │    │
│  │        │               │               │                      │    │
│  │        └───────────────┼───────────────┘                      │    │
│  │                        │                                      │    │
│  │                   Payment URL                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  PAYMENT WEBHOOKS                             │    │
│  │                                                               │    │
│  │  POST /webhooks/stripe/{tenant_slug}                          │    │
│  │  POST /webhooks/hotmart/{tenant_slug}                         │    │
│  │  POST /webhooks/kiwify/{tenant_slug}                          │    │
│  │                                                               │    │
│  │  → Atualiza pedido (paid/refunded/expired)                    │    │
│  │  → Atualiza contato no CRM                                   │    │
│  │  → Notifica cliente via WhatsApp                              │    │
│  │  → Entrega produto digital (se aplicável)                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              ABANDONED CART SCHEDULER                          │    │
│  │              (APScheduler - a cada 30 min)                    │    │
│  │                                                               │    │
│  │  → Busca carrinhos sem pedido há X horas                      │    │
│  │  → Envia lembrete personalizado via WhatsApp                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     POSTGRESQL (Multi-tenant)                        │
│                                                                      │
│  tenants ─┬─ channels ─── ai_configs                                │
│           ├─ contacts ──┬─ messages                                  │
│           │             ├─ cart_items                                 │
│           │             ├─ orders ──── order_items                   │
│           │             └─ sales_conversations                       │
│           ├─ products ──── product_variants                          │
│           ├─ coupons                                                 │
│           ├─ payment_events                                          │
│           └─ token_usage                                             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Fluxo de Venda Completo

```
Cliente: "Oi, tem camisa do Brasil?"
    │
    ▼ IA chama search_products("camisa brasil")
    │
IA: "Temos sim! 🇧🇷 Camisa Brasil 2026 por R$89,90 (de R$129,90 - 31% OFF)
     Tamanhos: P, M, G, GG. Qual o seu?"
    │ [envia imagem do produto]
    │
Cliente: "Quero M. Tem kit com 6 unidades?"
    │
    ▼ IA chama check_stock(product_id=1, quantity=6)
    ▼ IA chama add_to_cart(product_id=1, variant_id=3, quantity=6)
    │ (preço atacado aplicado automaticamente: R$59,90/un)
    │
IA: "Kit montado! 🛒 6x Camisa Brasil M = R$359,40 (preço atacado!)
     Normal seria R$539,40 — economia de R$180! 
     Quer adicionar mais alguma coisa?"
    │
Cliente: "Não, pode fechar!"
    │
    ▼ IA chama create_order_and_payment_link()
    │
IA: "Pedido VF-X8K2M9 criado! 🎉
     Total: R$359,40

     💳 Link de Pagamento:
     https://checkout.stripe.com/c/pay/cs_live_...
     
     ✅ Pague via Pix, cartão ou boleto."
    │
    ▼ [Cliente paga]
    │
    ▼ [Webhook Stripe → payment approved]
    │
IA: "Pagamento confirmado! ✅ Pedido VF-X8K2M9 aprovado.
     Vamos preparar seu kit para envio. Obrigada pela compra! 🎉"
```

---

## Estrutura de Arquivos

```
vendaflow/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app
│   │   ├── database.py                # SQLAlchemy async config
│   │   ├── models.py                  # Todos os models
│   │   ├── evolution_client.py        # WhatsApp via Evolution API
│   │   │
│   │   ├── agents/                    # Agentes de IA
│   │   │   ├── __init__.py
│   │   │   ├── sales_agent.py         # ★ CORE: agente de vendas
│   │   │   ├── tools.py              # Function calling tools
│   │   │   ├── executor.py           # Executor das tools
│   │   │   └── abandoned_cart.py     # Scheduler carrinho abandonado
│   │   │
│   │   ├── gateways/                  # Integrações de pagamento
│   │   │   ├── __init__.py           # Base abstraction
│   │   │   ├── factory.py           # Gateway factory
│   │   │   ├── stripe_gw.py         # Stripe integration
│   │   │   ├── hotmart_gw.py        # Hotmart integration
│   │   │   └── kiwify_gw.py         # Kiwify integration
│   │   │
│   │   └── webhooks/                  # Webhooks
│   │       ├── __init__.py
│   │       ├── evolution_routes.py   # WhatsApp webhook
│   │       └── payment_webhooks.py   # Stripe/Hotmart/Kiwify webhooks
│   │
│   ├── migration.sql                  # Schema do banco
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/                          # Next.js (a construir)
    └── ... (mesma estrutura do EduFlow)
```

---

## Como Rodar

### 1. Banco de Dados
```bash
createdb vendaflow_db
psql vendaflow_db < backend/migration.sql
```

### 2. Backend
```bash
cd backend
cp .env.example .env
# Editar .env com suas chaves
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Configurar Evolution API
No painel do Evolution, configure o webhook da instância:
```
URL: https://seudominio.com/evolution/webhook/{instance_name}
Events: MESSAGES_UPSERT
```

### 4. Configurar Webhooks de Pagamento

**Stripe:**
```
URL: https://seudominio.com/webhooks/stripe/{tenant_slug}
Events: checkout.session.completed, payment_intent.succeeded, 
        payment_intent.payment_failed, charge.refunded
```

**Hotmart:**
```
URL: https://seudominio.com/webhooks/hotmart/{tenant_slug}
Events: PURCHASE_COMPLETE, PURCHASE_CANCELED, PURCHASE_REFUNDED
```

**Kiwify:**
```
URL: https://seudominio.com/webhooks/kiwify/{tenant_slug}
Events: order_approved, order_refunded
```

---

## Diferença Técnica EduFlow → VendaFlow

| Aspecto | EduFlow | VendaFlow |
|---------|---------|-----------|
| AI Output | JSON com message/collected/action | Function calling com tools |
| Tools | Nenhuma (output puro) | 13 tools de venda |
| Pagamento | Nenhum | Stripe + Hotmart + Kiwify |
| Carrinho | Não existe | CartItem + sessão |
| Pedidos | Não existe | Order + OrderItem |
| Catálogo | Não existe | Products + Variants + Categories |
| Cupons | Não existe | Coupons com validação |
| Pipeline | Educacional (matrícula) | E-commerce (carrinho → pago → enviado) |
| Scheduler | Followup/Reativação | Carrinho abandonado |
| Webhooks | Só Evolution | Evolution + Stripe + Hotmart + Kiwify |

---

## Casos de Uso

### 1. Camisas de Seleções/Times (Físico)
- Catálogo com variantes (tamanho, cor)
- Preço varejo + atacado
- Estoque controlado
- Stripe para pagamento
- Pós-venda: tracking code

### 2. Kits de Blusas Atacado (Físico)
- Quantidade mínima para preço atacado
- Descontos progressivos
- IA identifica cliente atacado automaticamente

### 3. Produtos Digitais Low Ticket
- Hotmart ou Kiwify como gateway
- Entrega automática após pagamento
- Link de acesso enviado via WhatsApp

---

## Próximos Passos (Roadmap)

- [ ] Rotas CRUD do frontend (Products, Orders, Contacts, Dashboard)
- [ ] Dashboard de vendas com métricas em tempo real
- [ ] Catálogo visual no frontend para cadastro de produtos
- [ ] Tela de pedidos com status e rastreio
- [ ] Integração com Correios/Melhor Envio para frete
- [ ] Pós-venda automático (pesquisa de satisfação)
- [ ] Upsell inteligente baseado em histórico
- [ ] Relatórios de conversão por canal/produto
- [ ] App mobile para gestão de pedidos
