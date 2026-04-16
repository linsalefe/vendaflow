"""
VendaFlow AI — Models
CRM de vendas com IA que vai até o checkout.
Baseado na arquitetura EduFlow (multi-tenant, WhatsApp, AI agents).
"""
from sqlalchemy import (
    Column, String, Text, DateTime, BigInteger, Integer, Boolean,
    ForeignKey, func, Table, Numeric, UniqueConstraint, JSON, Float, Enum
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class ProductType(str, enum.Enum):
    PHYSICAL = "physical"
    DIGITAL = "digital"

class OrderStatus(str, enum.Enum):
    DRAFT = "draft"                # carrinho montado pela IA
    PENDING = "pending"            # link de pagamento gerado
    PAID = "paid"                  # pagamento confirmado
    PROCESSING = "processing"      # em separação (físico)
    SHIPPED = "shipped"            # enviado (físico)
    DELIVERED = "delivered"        # entregue
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class PaymentGateway(str, enum.Enum):
    STRIPE = "stripe"
    HOTMART = "hotmart"
    KIWIFY = "kiwify"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REFUSED = "refused"
    REFUNDED = "refunded"
    EXPIRED = "expired"


# ─────────────────────────────────────────────────────────────────────────────
# CORE CRM (adaptado do EduFlow)
# ─────────────────────────────────────────────────────────────────────────────

contact_tags = Table(
    "contact_tags",
    Base.metadata,
    Column("contact_wa_id", String(20), ForeignKey("contacts.wa_id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Tenant(Base):
    """Cada loja/operação é um tenant."""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    domain = Column(String(255), nullable=True)
    logo_url = Column(String(500), nullable=True)
    
    # Config de pagamento
    stripe_secret_key = Column(Text, nullable=True)
    stripe_webhook_secret = Column(Text, nullable=True)
    hotmart_token = Column(Text, nullable=True)
    hotmart_hottok = Column(Text, nullable=True)
    kiwify_api_key = Column(Text, nullable=True)
    kiwify_webhook_secret = Column(Text, nullable=True)
    default_gateway = Column(String(20), default="stripe")
    
    # Config da IA de vendas
    ai_sales_prompt = Column(Text, nullable=True)
    ai_model = Column(String(50), default="gpt-4.1")
    ai_temperature = Column(Float, default=0.4)
    ai_personality = Column(String(100), default="vendedora_amigavel")
    
    # Mensagens customizáveis
    welcome_message = Column(Text, nullable=True)
    post_sale_message = Column(Text, nullable=True)
    abandoned_cart_message = Column(Text, nullable=True)
    
    # Features e controle
    features = Column(JSON, default={
        "ai_sales": True,
        "catalog_whatsapp": True,
        "abandoned_cart": True,
        "post_sale_followup": True,
        "upsell_engine": True,
        "wholesale_pricing": True,
        "digital_delivery": True,
        "shipping_calc": False,
    })
    
    kanban_columns = Column(JSON, default=[
        {"key": "novo", "label": "Novo Lead", "color": "#6366f1", "order": 0},
        {"key": "interessado", "label": "Interessado", "color": "#f59e0b", "order": 1},
        {"key": "carrinho", "label": "Carrinho Montado", "color": "#8b5cf6", "order": 2},
        {"key": "link_enviado", "label": "Link Enviado", "color": "#06b6d4", "order": 3},
        {"key": "pago", "label": "Pago", "color": "#10b981", "order": 4},
        {"key": "enviado", "label": "Enviado", "color": "#3b82f6", "order": 5},
        {"key": "entregue", "label": "Entregue", "color": "#22c55e", "order": 6},
        {"key": "perdido", "label": "Perdido", "color": "#ef4444", "order": 7},
    ])
    
    # Metas
    monthly_revenue_goal = Column(Numeric(12, 2), default=0)
    monthly_orders_goal = Column(Integer, default=0)
    
    # Créditos IA
    credits_balance = Column(Integer, default=1000)
    credits_used = Column(Integer, default=0)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="tenant")
    channels = relationship("Channel", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")
    orders = relationship("Order", back_populates="tenant")


class Channel(Base):
    """Canal de comunicação (WhatsApp via Evolution API, Instagram, etc)."""
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(String(20), default="whatsapp")  # whatsapp, instagram, telegram
    provider = Column(String(20), default="evolution")  # evolution, official
    
    # Evolution API
    instance_name = Column(String(100), nullable=True)
    instance_token = Column(Text, nullable=True)
    
    # WhatsApp Business API (oficial)
    phone_number = Column(String(20), nullable=True)
    phone_number_id = Column(String(50), nullable=True)
    whatsapp_token = Column(Text, nullable=True)
    waba_id = Column(String(50), nullable=True)
    
    # Instagram
    page_id = Column(String(50), nullable=True)
    instagram_id = Column(String(50), nullable=True)
    access_token = Column(Text, nullable=True)
    
    is_connected = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    tenant = relationship("Tenant", back_populates="channels")
    contacts = relationship("Contact", back_populates="channel")
    messages = relationship("Message", back_populates="channel")


class Contact(Base):
    """Lead/Cliente."""
    __tablename__ = "contacts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    wa_id = Column(String(20), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    cpf = Column(String(14), nullable=True)
    profile_picture_url = Column(String, nullable=True)
    
    # Pipeline de vendas
    lead_status = Column(String(30), default="novo")
    
    # Dados de endereço (para produtos físicos)
    address_cep = Column(String(10), nullable=True)
    address_street = Column(String(255), nullable=True)
    address_number = Column(String(20), nullable=True)
    address_complement = Column(String(100), nullable=True)
    address_city = Column(String(100), nullable=True)
    address_state = Column(String(2), nullable=True)
    
    # IA
    ai_active = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)  # JSON com dados coletados pela IA
    
    # Métricas
    total_orders = Column(Integer, default=0)
    total_spent = Column(Numeric(12, 2), default=0)
    last_order_at = Column(DateTime, nullable=True)
    last_inbound_at = Column(DateTime, nullable=True)
    
    channel_id = Column(Integer, ForeignKey("channels.id"))
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    is_wholesale = Column(Boolean, default=False)  # cliente atacado
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    messages = relationship("Message", back_populates="contact")
    tags = relationship("Tag", secondary=contact_tags, back_populates="contacts")
    channel = relationship("Channel", back_populates="contacts")
    orders = relationship("Order", back_populates="contact")
    cart_items = relationship("CartItem", back_populates="contact")


class Message(Base):
    """Mensagens trocadas."""
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    wa_message_id = Column(String(255), unique=True, nullable=False, index=True)
    contact_wa_id = Column(String(20), ForeignKey("contacts.wa_id"), nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"))
    direction = Column(String(10), nullable=False)  # inbound, outbound
    message_type = Column(String(20), nullable=False)  # text, image, audio, document
    content = Column(Text, nullable=True)
    media_url = Column(String(500), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    status = Column(String(20), default="received")
    sent_by_ai = Column(Boolean, default=False)
    sender_name = Column(String(255), nullable=True)
    
    # Metadados de venda
    related_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    ai_action = Column(String(50), nullable=True)  # show_product, add_cart, send_link, etc.
    
    created_at = Column(DateTime, server_default=func.now())

    contact = relationship("Contact", back_populates="messages")
    channel = relationship("Channel", back_populates="messages")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tag_tenant_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(50), nullable=False)
    color = Column(String(20), nullable=False, default="blue")
    created_at = Column(DateTime, server_default=func.now())

    contacts = relationship("Contact", secondary=contact_tags, back_populates="tags")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="vendedor")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    tenant = relationship("Tenant", back_populates="users")


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO DE PRODUTOS
# ─────────────────────────────────────────────────────────────────────────────

class ProductCategory(Base):
    """Categorias de produto."""
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    parent_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    products = relationship("Product", back_populates="category")


class Product(Base):
    """Produto (físico ou digital)."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    short_description = Column(String(500), nullable=True)  # para a IA usar no WhatsApp
    
    product_type = Column(String(20), default="physical")  # physical, digital
    
    # Preços
    price = Column(Numeric(10, 2), nullable=False)  # preço varejo
    wholesale_price = Column(Numeric(10, 2), nullable=True)  # preço atacado
    wholesale_min_qty = Column(Integer, default=6)  # quantidade mínima para atacado
    compare_at_price = Column(Numeric(10, 2), nullable=True)  # preço "de" (riscado)
    cost_price = Column(Numeric(10, 2), nullable=True)  # custo
    
    # Estoque (para físicos)
    track_stock = Column(Boolean, default=True)
    stock_quantity = Column(Integer, default=0)
    low_stock_alert = Column(Integer, default=5)
    
    # Peso/dimensões (para frete)
    weight_grams = Column(Integer, nullable=True)
    
    # Digital
    digital_file_url = Column(String(500), nullable=True)  # link do arquivo
    digital_access_days = Column(Integer, nullable=True)  # dias de acesso
    
    # Imagens
    image_url = Column(String(500), nullable=True)  # imagem principal
    images = Column(JSON, default=[])  # galeria: ["url1", "url2"]
    
    # Gateway específico (override do tenant)
    gateway_override = Column(String(20), nullable=True)  # stripe, hotmart, kiwify
    external_product_id = Column(String(255), nullable=True)  # ID no Hotmart/Kiwify
    external_offer_id = Column(String(255), nullable=True)  # Offer ID (Hotmart)
    
    # Variantes como JSON (tamanho, cor, etc.)
    has_variants = Column(Boolean, default=False)
    variant_options = Column(JSON, default=[])
    # Ex: [{"name": "Tamanho", "values": ["P","M","G","GG"]}, {"name": "Cor", "values": ["Branco","Preto"]}]
    
    # IA
    ai_selling_points = Column(Text, nullable=True)  # argumentos de venda para a IA
    ai_objection_responses = Column(JSON, default={})
    # Ex: {"caro": "Entendo! Mas olha, comparado com...", "frete": "Frete grátis acima de R$150!"}
    
    # SEO / tags para busca da IA
    search_tags = Column(JSON, default=[])  # ["seleção brasil", "copa", "nike"]
    
    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="products")
    category = relationship("ProductCategory", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product")


class ProductVariant(Base):
    """Variantes do produto (ex: Camisa Brasil M Branca)."""
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    
    sku = Column(String(100), nullable=True)
    variant_label = Column(String(255), nullable=False)  # "M / Branco"
    variant_options = Column(JSON, default={})  # {"Tamanho": "M", "Cor": "Branco"}
    
    price_override = Column(Numeric(10, 2), nullable=True)
    stock_quantity = Column(Integer, default=0)
    image_url = Column(String(500), nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    product = relationship("Product", back_populates="variants")


# ─────────────────────────────────────────────────────────────────────────────
# CARRINHO + PEDIDOS
# ─────────────────────────────────────────────────────────────────────────────

class CartItem(Base):
    """Carrinho do lead (gerenciado pela IA durante a conversa)."""
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    contact_wa_id = Column(String(20), ForeignKey("contacts.wa_id"), nullable=False, index=True)
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    
    created_at = Column(DateTime, server_default=func.now())

    contact = relationship("Contact", back_populates="cart_items")
    product = relationship("Product")
    variant = relationship("ProductVariant")


class Order(Base):
    """Pedido de venda."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    contact_wa_id = Column(String(20), ForeignKey("contacts.wa_id"), nullable=False, index=True)
    
    # Número do pedido legível
    order_number = Column(String(20), unique=True, nullable=False)
    
    status = Column(String(20), default="draft")
    
    # Valores
    subtotal = Column(Numeric(12, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    shipping_cost = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(12, 2), nullable=False, default=0)
    
    # Pagamento
    payment_gateway = Column(String(20), nullable=True)
    payment_link = Column(String(500), nullable=True)
    payment_link_id = Column(String(255), nullable=True)  # ID no gateway
    payment_status = Column(String(20), default="pending")
    paid_at = Column(DateTime, nullable=True)
    
    # Endereço de entrega (snapshot)
    shipping_address = Column(JSON, nullable=True)
    tracking_code = Column(String(100), nullable=True)
    
    # Cupom
    coupon_code = Column(String(50), nullable=True)
    
    # Digital delivery
    digital_access_url = Column(String(500), nullable=True)
    digital_access_sent = Column(Boolean, default=False)
    
    # Notas
    notes = Column(Text, nullable=True)
    ai_generated = Column(Boolean, default=True)  # pedido criado pela IA
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="orders")
    contact = relationship("Contact", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    """Itens do pedido."""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)
    
    product_name = Column(String(255), nullable=False)  # snapshot
    variant_label = Column(String(255), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    
    created_at = Column(DateTime, server_default=func.now())

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")


# ─────────────────────────────────────────────────────────────────────────────
# PAGAMENTOS
# ─────────────────────────────────────────────────────────────────────────────

class PaymentEvent(Base):
    """Log de eventos de pagamento (webhooks)."""
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    gateway = Column(String(20), nullable=False)
    event_type = Column(String(100), nullable=False)  # payment_intent.succeeded, etc
    gateway_event_id = Column(String(255), nullable=True)
    payload = Column(JSON, nullable=True)
    
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Coupon(Base):
    """Cupons de desconto."""
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False)
    discount_type = Column(String(20), default="percentage")  # percentage, fixed
    discount_value = Column(Numeric(10, 2), nullable=False)
    min_order_value = Column(Numeric(10, 2), nullable=True)
    max_uses = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# IA CONFIG
# ─────────────────────────────────────────────────────────────────────────────

class AIConfig(Base):
    """Configuração da IA por canal."""
    __tablename__ = "ai_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), unique=True, nullable=False)
    
    is_enabled = Column(Boolean, default=True)
    system_prompt = Column(Text, nullable=True)
    model = Column(String(50), default="gpt-4.1")
    temperature = Column(String(10), default="0.4")
    max_tokens = Column(Integer, default=600)
    
    # Comportamento
    auto_send_catalog = Column(Boolean, default=True)  # enviar catálogo automaticamente
    auto_generate_link = Column(Boolean, default=True)  # gerar link sem pedir permissão
    upsell_enabled = Column(Boolean, default=True)
    abandoned_cart_hours = Column(Integer, default=2)  # horas para enviar lembrete
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    channel = relationship("Channel", backref="ai_config")


class KnowledgeDocument(Base):
    """Base de conhecimento para RAG."""
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)
    chunk_index = Column(Integer, default=0)
    token_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class SalesConversation(Base):
    """Rastreamento do fluxo de venda pela IA."""
    __tablename__ = "sales_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    contact_wa_id = Column(String(20), ForeignKey("contacts.wa_id"), nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    
    # Estado da venda
    stage = Column(String(50), default="greeting")
    # greeting → browsing → product_selected → cart_built → link_sent → paid → delivered
    
    # Contexto coletado
    interests = Column(JSON, default=[])        # ["camisa brasil", "kit atacado"]
    objections = Column(JSON, default=[])        # ["preço alto", "frete caro"]
    preferences = Column(JSON, default={})       # {"tamanho": "M", "cor": "azul"}
    
    # Referência ao pedido
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    # Métricas
    messages_count = Column(Integer, default=0)
    started_at = Column(DateTime, server_default=func.now())
    converted_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TokenUsage(Base):
    """Consumo de tokens IA."""
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(50), nullable=False, default="sales_ai")
    model = Column(String(100), nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
