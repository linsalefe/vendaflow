# VendaFlow AI 🛒🤖

## CRM de Vendas com IA que vai do Atendimento ao Checkout

**Stack:** FastAPI + Next.js 16 + PostgreSQL + OpenAI (function calling) + Evolution API (WhatsApp)

---

## O que é

VendaFlow AI é um CRM de vendas onde a **IA é a vendedora**. Ela conversa com o cliente pelo WhatsApp, mostra produtos do catálogo, monta carrinho, aplica cupom, gera link de pagamento e faz pós-venda — tudo automaticamente, 24 horas por dia.

### Para quem é
- Quem vende **produtos físicos** (camisas, acessórios, moda)
- Quem vende **low ticket digital** (cursos de R$47 a R$87)
- Quem quer automatizar vendas pelo WhatsApp sem equipe

### Diferenciais
| CRM Tradicional | VendaFlow AI |
|-----------------|-------------|
| IA qualifica leads | IA **fecha vendas** |
| Agente agenda reunião | Agente **gera link de pagamento** |
| Sem catálogo | **Catálogo completo** com variantes |
| Sem pagamento | **Stripe + Hotmart + Kiwify + MercadoPago** |
| Pipeline genérico | Pipeline de **e-commerce** (carrinho → pago → enviado) |

---

## Arquitetura

```
Cliente (WhatsApp) → Evolution API → VendaFlow Backend (FastAPI)
                                          │
                                    Sales Agent (GPT + Function Calling)
                                          │
                                    ┌─────┼─────┐
                                    │     │     │
                              search_products  add_to_cart  create_order
                                    │     │     │
                              Catálogo  Carrinho  Gateway de Pagamento
                                                  (Stripe/Hotmart/Kiwify/MP)
                                          │
                                    Resposta + Link de Pagamento
                                          │
                                    Evolution API → Cliente (WhatsApp)
```

---

## Stack Técnica

### Backend
- **FastAPI** — API async, 141+ rotas
- **SQLAlchemy** (async) — ORM com PostgreSQL
- **OpenAI** — GPT com function calling (13 tools de venda)
- **APScheduler** — Carrinho abandonado automático (a cada 30 min)
- **Stripe/Hotmart/Kiwify/MercadoPago** — Gateways de pagamento
- **Evolution API** — WhatsApp (envio/recebimento)
- **ElevenLabs** — Resposta em áudio (feature flag)

### Frontend
- **Next.js 16** (App Router, React 19)
- **Tailwind CSS 4** + **shadcn/ui**
- **Recharts** — Gráficos de dashboard
- **Tanstack Table** — Tabelas com filtro/paginação
- Dark theme com identidade verde/dourado (money green)

### Infraestrutura
- **PostgreSQL 16** — 36 tabelas (multi-tenant)
- **Nginx** — Reverse proxy
- **PM2** — Process manager
- **Git** — Versionamento

---

## Estrutura de Arquivos

```
vendaflow/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app (141 rotas)
│   │   ├── database.py              # SQLAlchemy async
│   │   ├── models.py                # Models base (EduFlow)
│   │   ├── sales_models.py          # Models de venda (VendaFlow)
│   │   ├── auth.py                  # JWT auth
│   │   ├── auth_routes.py           # Login, register, profile
│   │   ├── routes.py                # CRUD contacts, messages, channels
│   │   ├── product_routes.py        # CRUD produtos, categorias, variantes
│   │   ├── order_routes.py          # Gestão de pedidos
│   │   ├── coupon_routes.py         # CRUD cupons + validação
│   │   ├── gateway_routes.py        # Config gateways (admin)
│   │   ├── tenant_routes.py         # Multi-tenant management
│   │   ├── kanban_routes.py         # Pipeline/Kanban
│   │   ├── ai_routes.py             # Config IA por canal
│   │   ├── ai_engine.py             # AI Engine base
│   │   ├── evolution_client.py      # Client WhatsApp (send text/image)
│   │   ├── agents/
│   │   │   ├── sales_agent.py       # ★ CORE: agente de vendas (function calling)
│   │   │   ├── tools.py             # 13 tools do agente
│   │   │   ├── executor.py          # Executor das tools
│   │   │   └── abandoned_cart.py    # Scheduler carrinho abandonado
│   │   ├── gateways/
│   │   │   ├── factory.py           # Gateway factory pattern
│   │   │   ├── stripe_gw.py
│   │   │   ├── hotmart_gw.py
│   │   │   └── kiwify_gw.py
│   │   ├── webhooks/
│   │   │   └── payment_webhooks.py  # Stripe/Hotmart/Kiwify webhooks
│   │   ├── evolution/               # Evolution API (instâncias + webhook)
│   │   └── elevenlabs/              # TTS (feature flag)
│   ├── init_db.py                   # Criar/resetar banco
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── login/               # Tela de login
│   │   │   ├── dashboard/           # Dashboard principal
│   │   │   ├── conversations/       # Chat WhatsApp
│   │   │   ├── contatos/            # Gestão de contatos
│   │   │   ├── pipeline/            # Pipeline visual
│   │   │   ├── kanban/              # Kanban board
│   │   │   ├── produtos/            # ★ Catálogo de produtos
│   │   │   ├── pedidos/             # ★ Gestão de pedidos
│   │   │   ├── cupons/              # ★ Cupons de desconto
│   │   │   ├── gateways/            # ★ Config pagamento
│   │   │   ├── ai-config/           # Config IA por canal
│   │   │   ├── canais/              # Gestão WhatsApp
│   │   │   ├── users/               # Gestão usuários
│   │   │   └── configuracoes/       # Config da conta
│   │   ├── components/              # shadcn/ui + custom
│   │   ├── contexts/                # Auth + Theme
│   │   ├── hooks/
│   │   └── lib/                     # API client, utils
│   └── package.json
│
├── .gitignore
└── README.md
```

---

## Fluxo de Venda (exemplo real)

```
Cliente: "Oi, tem camisa preta?"
    │
    ▼ IA chama search_products("camisa preta")
    │
IA: "Temos sim! 🖤 Kit Camisa Preta por R$120,00 (4 unidades).
     Tamanhos: P, M, G, GG. Qual o seu?"
    │ [envia imagem do produto]
    │
Cliente: "Quero G, 2 kits"
    │
    ▼ IA chama add_to_cart(product_id=1, variant="G", quantity=2)
    │
IA: "Carrinho montado! 🛒 2x Kit Camisa Preta G = R$240,00.
     Quer adicionar mais algo?"
    │
Cliente: "Não, pode fechar"
    │
    ▼ IA chama create_order_and_payment_link()
    │
IA: "Pedido VF-X8K2 criado! 🎉
     💳 Link: https://checkout.stripe.com/...
     ✅ Pague via Pix, cartão ou boleto."
    │
    ▼ [Cliente paga → Webhook confirma]
    │
IA: "Pagamento confirmado! ✅ Preparando envio. Obrigada! 🎉"
```

---

## Como Rodar

### 1. Pré-requisitos
- Python 3.11+
- Node.js 20+
- PostgreSQL 14+
- Evolution API (WhatsApp)
- Chave OpenAI

### 2. Banco de Dados
```bash
# Criar user e banco
sudo -u postgres psql <<EOF
CREATE USER vendaflow_user WITH PASSWORD 'SUA_SENHA';
CREATE DATABASE vendaflow OWNER vendaflow_user;
GRANT ALL PRIVILEGES ON DATABASE vendaflow TO vendaflow_user;
EOF

# Criar tabelas
cd backend
cp .env.example .env
# Editar .env com suas chaves
source venv/bin/activate
python init_db.py create
```

### 3. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload
```

### 4. Frontend
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8100/api" > .env.local
npm run dev
```

### 5. Configurar Evolution API
No painel do Evolution, configure o webhook da instância:
```
URL: https://seudominio.com/api/evolution/webhook/{instance_name}
Events: MESSAGES_UPSERT, CONNECTION_UPDATE
```

### 6. Deploy (VPS)
```bash
# PM2 para manter rodando
pm2 start "source venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8100" --name vendaflow-backend
pm2 start "npm run start -- -p 3100" --name vendaflow-frontend
pm2 save && pm2 startup

# Nginx reverse proxy
# Frontend: / → localhost:3100
# Backend:  /api/ → localhost:8100
```

---

## Variáveis de Ambiente (.env)

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | PostgreSQL connection string |
| `FRONTEND_URL` | URL do frontend |
| `OPENAI_API_KEY` | Chave API OpenAI |
| `EVOLUTION_API_URL` | URL da Evolution API |
| `EVOLUTION_API_KEY` | API Key do Evolution |
| `JWT_SECRET_KEY` | Secret JWT (gerar com `openssl rand -hex 32`) |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_EXPIRATION_HOURS` | `24` |
| `ELEVENLABS_API_KEY` | (opcional) Para respostas em áudio |

---

## Tools do Sales Agent (Function Calling)

| Tool | Descrição |
|------|-----------|
| `search_products` | Buscar produtos no catálogo |
| `get_product_details` | Detalhes + imagens de um produto |
| `check_stock` | Verificar estoque disponível |
| `add_to_cart` | Adicionar item ao carrinho |
| `remove_from_cart` | Remover item do carrinho |
| `view_cart` | Ver resumo do carrinho |
| `apply_coupon` | Validar e aplicar cupom de desconto |
| `create_order_and_payment_link` | Criar pedido e gerar link de pagamento |
| `collect_customer_data` | Salvar dados do cliente (nome, email, endereço) |
| `move_pipeline` | Mover lead no pipeline de vendas |
| `get_upsell_suggestions` | Sugerir produtos complementares |
| `get_order_status` | Verificar status de um pedido |
| `search_faq` | Buscar na base de conhecimento |

---

## Pipeline de Vendas

```
Novo Lead → Interessado → Carrinho Montado → Link Enviado → Pago → Enviado → Entregue
                                                                          ↓
                                                                       Perdido
```

---

## Licença

Projeto privado — uso comercial autorizado pelo proprietário.
