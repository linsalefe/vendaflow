-- =====================================================================
-- VendaFlow AI — Migration SQL
-- CRM de vendas com IA que vai até o checkout
-- Baseado na arquitetura EduFlow (multi-tenant)
-- =====================================================================

-- Extensão para UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── TENANTS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(255),
    logo_url VARCHAR(500),
    
    -- Gateways de pagamento
    stripe_secret_key TEXT,
    stripe_webhook_secret TEXT,
    hotmart_token TEXT,
    hotmart_hottok TEXT,
    kiwify_api_key TEXT,
    kiwify_webhook_secret TEXT,
    default_gateway VARCHAR(20) DEFAULT 'stripe',
    
    -- IA de vendas
    ai_sales_prompt TEXT,
    ai_model VARCHAR(50) DEFAULT 'gpt-4.1',
    ai_temperature FLOAT DEFAULT 0.4,
    ai_personality VARCHAR(100) DEFAULT 'vendedora_amigavel',
    
    -- Mensagens customizáveis
    welcome_message TEXT,
    post_sale_message TEXT,
    abandoned_cart_message TEXT,
    
    -- Features
    features JSONB DEFAULT '{
        "ai_sales": true,
        "catalog_whatsapp": true,
        "abandoned_cart": true,
        "post_sale_followup": true,
        "upsell_engine": true,
        "wholesale_pricing": true,
        "digital_delivery": true,
        "shipping_calc": false
    }'::jsonb,
    
    -- Pipeline
    kanban_columns JSONB DEFAULT '[
        {"key": "novo", "label": "Novo Lead", "color": "#6366f1", "order": 0},
        {"key": "interessado", "label": "Interessado", "color": "#f59e0b", "order": 1},
        {"key": "carrinho", "label": "Carrinho Montado", "color": "#8b5cf6", "order": 2},
        {"key": "link_enviado", "label": "Link Enviado", "color": "#06b6d4", "order": 3},
        {"key": "pago", "label": "Pago", "color": "#10b981", "order": 4},
        {"key": "enviado", "label": "Enviado", "color": "#3b82f6", "order": 5},
        {"key": "entregue", "label": "Entregue", "color": "#22c55e", "order": 6},
        {"key": "perdido", "label": "Perdido", "color": "#ef4444", "order": 7}
    ]'::jsonb,
    
    -- Metas
    monthly_revenue_goal NUMERIC(12,2) DEFAULT 0,
    monthly_orders_goal INTEGER DEFAULT 0,
    
    -- Créditos IA
    credits_balance INTEGER DEFAULT 1000,
    credits_used INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ─── USERS ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'vendedor',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── CHANNELS ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) DEFAULT 'whatsapp',
    provider VARCHAR(20) DEFAULT 'evolution',
    
    -- Evolution API
    instance_name VARCHAR(100),
    instance_token TEXT,
    
    -- WhatsApp Business API
    phone_number VARCHAR(20),
    phone_number_id VARCHAR(50),
    whatsapp_token TEXT,
    waba_id VARCHAR(50),
    
    -- Instagram
    page_id VARCHAR(50),
    instagram_id VARCHAR(50),
    access_token TEXT,
    
    is_connected BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── CONTACTS ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS contacts (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    wa_id VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    email VARCHAR(255),
    cpf VARCHAR(14),
    profile_picture_url TEXT,
    
    lead_status VARCHAR(30) DEFAULT 'novo',
    
    -- Endereço
    address_cep VARCHAR(10),
    address_street VARCHAR(255),
    address_number VARCHAR(20),
    address_complement VARCHAR(100),
    address_city VARCHAR(100),
    address_state VARCHAR(2),
    
    -- IA
    ai_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    
    -- Métricas
    total_orders INTEGER DEFAULT 0,
    total_spent NUMERIC(12,2) DEFAULT 0,
    last_order_at TIMESTAMP,
    last_inbound_at TIMESTAMP,
    
    channel_id INTEGER REFERENCES channels(id),
    assigned_to INTEGER REFERENCES users(id),
    is_wholesale BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contacts_wa_id ON contacts(wa_id);
CREATE INDEX IF NOT EXISTS idx_contacts_tenant ON contacts(tenant_id);

-- ─── TAGS ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    name VARCHAR(50) NOT NULL,
    color VARCHAR(20) NOT NULL DEFAULT 'blue',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

CREATE TABLE IF NOT EXISTS contact_tags (
    contact_wa_id VARCHAR(20) REFERENCES contacts(wa_id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (contact_wa_id, tag_id)
);

-- ─── MESSAGES ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    wa_message_id VARCHAR(255) UNIQUE NOT NULL,
    contact_wa_id VARCHAR(20) NOT NULL REFERENCES contacts(wa_id),
    channel_id INTEGER REFERENCES channels(id),
    direction VARCHAR(10) NOT NULL,
    message_type VARCHAR(20) NOT NULL,
    content TEXT,
    media_url VARCHAR(500),
    timestamp TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'received',
    sent_by_ai BOOLEAN DEFAULT FALSE,
    sender_name VARCHAR(255),
    related_order_id INTEGER,
    ai_action VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_wa_id ON messages(wa_message_id);
CREATE INDEX IF NOT EXISTS idx_messages_contact ON messages(contact_wa_id);

-- ─── PRODUCT CATEGORIES ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS product_categories (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT,
    image_url VARCHAR(500),
    parent_id INTEGER REFERENCES product_categories(id),
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── PRODUCTS ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    category_id INTEGER REFERENCES product_categories(id),
    
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT,
    short_description VARCHAR(500),
    
    product_type VARCHAR(20) DEFAULT 'physical',
    
    -- Preços
    price NUMERIC(10,2) NOT NULL,
    wholesale_price NUMERIC(10,2),
    wholesale_min_qty INTEGER DEFAULT 6,
    compare_at_price NUMERIC(10,2),
    cost_price NUMERIC(10,2),
    
    -- Estoque
    track_stock BOOLEAN DEFAULT TRUE,
    stock_quantity INTEGER DEFAULT 0,
    low_stock_alert INTEGER DEFAULT 5,
    
    -- Peso
    weight_grams INTEGER,
    
    -- Digital
    digital_file_url VARCHAR(500),
    digital_access_days INTEGER,
    
    -- Imagens
    image_url VARCHAR(500),
    images JSONB DEFAULT '[]'::jsonb,
    
    -- Gateway
    gateway_override VARCHAR(20),
    external_product_id VARCHAR(255),
    external_offer_id VARCHAR(255),
    
    -- Variantes
    has_variants BOOLEAN DEFAULT FALSE,
    variant_options JSONB DEFAULT '[]'::jsonb,
    
    -- IA
    ai_selling_points TEXT,
    ai_objection_responses JSONB DEFAULT '{}'::jsonb,
    search_tags JSONB DEFAULT '[]'::jsonb,
    
    is_active BOOLEAN DEFAULT TRUE,
    is_featured BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ─── PRODUCT VARIANTS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS product_variants (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    sku VARCHAR(100),
    variant_label VARCHAR(255) NOT NULL,
    variant_options JSONB DEFAULT '{}'::jsonb,
    price_override NUMERIC(10,2),
    stock_quantity INTEGER DEFAULT 0,
    image_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── CART ITEMS ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cart_items (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    contact_wa_id VARCHAR(20) NOT NULL REFERENCES contacts(wa_id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    variant_id INTEGER REFERENCES product_variants(id),
    quantity INTEGER DEFAULT 1,
    unit_price NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cart_contact ON cart_items(contact_wa_id);

-- ─── ORDERS ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    contact_wa_id VARCHAR(20) NOT NULL REFERENCES contacts(wa_id),
    order_number VARCHAR(20) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'draft',
    
    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,
    discount_amount NUMERIC(10,2) DEFAULT 0,
    shipping_cost NUMERIC(10,2) DEFAULT 0,
    total NUMERIC(12,2) NOT NULL DEFAULT 0,
    
    payment_gateway VARCHAR(20),
    payment_link VARCHAR(500),
    payment_link_id VARCHAR(255),
    payment_status VARCHAR(20) DEFAULT 'pending',
    paid_at TIMESTAMP,
    
    shipping_address JSONB,
    tracking_code VARCHAR(100),
    
    coupon_code VARCHAR(50),
    
    digital_access_url VARCHAR(500),
    digital_access_sent BOOLEAN DEFAULT FALSE,
    
    notes TEXT,
    ai_generated BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ─── ORDER ITEMS ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    variant_id INTEGER REFERENCES product_variants(id),
    product_name VARCHAR(255) NOT NULL,
    variant_label VARCHAR(255),
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(10,2) NOT NULL,
    total_price NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── PAYMENT EVENTS ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payment_events (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    order_id INTEGER REFERENCES orders(id),
    gateway VARCHAR(20) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    gateway_event_id VARCHAR(255),
    payload JSONB,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── COUPONS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS coupons (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    code VARCHAR(50) NOT NULL,
    discount_type VARCHAR(20) DEFAULT 'percentage',
    discount_value NUMERIC(10,2) NOT NULL,
    min_order_value NUMERIC(10,2),
    max_uses INTEGER,
    used_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── AI CONFIGS ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_configs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    channel_id INTEGER UNIQUE NOT NULL REFERENCES channels(id),
    is_enabled BOOLEAN DEFAULT TRUE,
    system_prompt TEXT,
    model VARCHAR(50) DEFAULT 'gpt-4.1',
    temperature VARCHAR(10) DEFAULT '0.4',
    max_tokens INTEGER DEFAULT 600,
    auto_send_catalog BOOLEAN DEFAULT TRUE,
    auto_generate_link BOOLEAN DEFAULT TRUE,
    upsell_enabled BOOLEAN DEFAULT TRUE,
    abandoned_cart_hours INTEGER DEFAULT 2,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ─── KNOWLEDGE DOCUMENTS (RAG) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    channel_id INTEGER NOT NULL REFERENCES channels(id),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding TEXT,
    chunk_index INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── SALES CONVERSATIONS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sales_conversations (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    contact_wa_id VARCHAR(20) NOT NULL REFERENCES contacts(wa_id),
    channel_id INTEGER NOT NULL REFERENCES channels(id),
    stage VARCHAR(50) DEFAULT 'greeting',
    interests JSONB DEFAULT '[]'::jsonb,
    objections JSONB DEFAULT '[]'::jsonb,
    preferences JSONB DEFAULT '{}'::jsonb,
    order_id INTEGER REFERENCES orders(id),
    messages_count INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT NOW(),
    converted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sales_conv_contact ON sales_conversations(contact_wa_id);

-- ─── TOKEN USAGE ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS token_usage (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL DEFAULT 'sales_ai',
    model VARCHAR(100),
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ─── INDEXES EXTRAS ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_orders_tenant ON orders(tenant_id);
CREATE INDEX IF NOT EXISTS idx_orders_contact ON orders(contact_wa_id);
CREATE INDEX IF NOT EXISTS idx_products_tenant ON products(tenant_id);
CREATE INDEX IF NOT EXISTS idx_payment_events_order ON payment_events(order_id);
