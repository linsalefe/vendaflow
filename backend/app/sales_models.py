"""
VendaFlow AI — Sales Models
Models específicos de venda (produtos, pedidos, cupons, pagamentos).
Importado por app.models.
"""
import enum
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Boolean,
    ForeignKey, func, Numeric, JSON, Float,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class ProductType(str, enum.Enum):
    PHYSICAL = "physical"
    DIGITAL = "digital"


class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentGateway(str, enum.Enum):
    STRIPE = "stripe"
    HOTMART = "hotmart"
    KIWIFY = "kiwify"
    MERCADOPAGO = "mercadopago"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REFUSED = "refused"
    REFUNDED = "refunded"
    EXPIRED = "expired"


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO
# ─────────────────────────────────────────────────────────────────────────────

class ProductCategory(Base):
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
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)

    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    short_description = Column(String(500), nullable=True)

    product_type = Column(String(20), default="physical")

    price = Column(Numeric(10, 2), nullable=False)
    wholesale_price = Column(Numeric(10, 2), nullable=True)
    wholesale_min_qty = Column(Integer, default=6)
    compare_at_price = Column(Numeric(10, 2), nullable=True)
    cost_price = Column(Numeric(10, 2), nullable=True)

    track_stock = Column(Boolean, default=True)
    stock_quantity = Column(Integer, default=0)
    low_stock_alert = Column(Integer, default=5)

    weight_grams = Column(Integer, nullable=True)

    digital_file_url = Column(String(500), nullable=True)
    digital_access_days = Column(Integer, nullable=True)

    image_url = Column(String(500), nullable=True)
    images = Column(JSON, default=list)

    gateway_override = Column(String(20), nullable=True)
    external_product_id = Column(String(255), nullable=True)
    external_offer_id = Column(String(255), nullable=True)

    has_variants = Column(Boolean, default=False)
    variant_options = Column(JSON, default=list)

    ai_selling_points = Column(Text, nullable=True)
    ai_objection_responses = Column(JSON, default=dict)

    search_tags = Column(JSON, default=list)

    is_active = Column(Boolean, default=True)
    is_featured = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    category = relationship("ProductCategory", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    sku = Column(String(100), nullable=True)
    variant_label = Column(String(255), nullable=False)
    variant_options = Column(JSON, default=dict)

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
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    contact_wa_id = Column(String(20), ForeignKey("contacts.wa_id"), nullable=False, index=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    product = relationship("Product")
    variant = relationship("ProductVariant")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    contact_wa_id = Column(String(20), ForeignKey("contacts.wa_id"), nullable=False, index=True)

    order_number = Column(String(20), unique=True, nullable=False)
    status = Column(String(20), default="draft")

    subtotal = Column(Numeric(12, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(10, 2), default=0)
    shipping_cost = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(12, 2), nullable=False, default=0)

    payment_gateway = Column(String(20), nullable=True)
    payment_link = Column(String(500), nullable=True)
    payment_link_id = Column(String(255), nullable=True)
    payment_status = Column(String(20), default="pending")
    paid_at = Column(DateTime, nullable=True)

    shipping_address = Column(JSON, nullable=True)
    tracking_code = Column(String(100), nullable=True)

    coupon_code = Column(String(50), nullable=True)

    digital_access_url = Column(String(500), nullable=True)
    digital_access_sent = Column(Boolean, default=False)

    notes = Column(Text, nullable=True)
    ai_generated = Column(Boolean, default=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)

    product_name = Column(String(255), nullable=False)
    variant_label = Column(String(255), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")


# ─────────────────────────────────────────────────────────────────────────────
# PAGAMENTOS + CUPONS
# ─────────────────────────────────────────────────────────────────────────────

class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)

    gateway = Column(String(20), nullable=False)
    event_type = Column(String(100), nullable=False)
    gateway_event_id = Column(String(255), nullable=True)
    payload = Column(JSON, nullable=True)

    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    code = Column(String(50), nullable=False)
    discount_type = Column(String(20), default="percentage")
    discount_value = Column(Numeric(10, 2), nullable=False)
    min_order_value = Column(Numeric(10, 2), nullable=True)
    max_uses = Column(Integer, nullable=True)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# RASTREAMENTO DA VENDA
# ─────────────────────────────────────────────────────────────────────────────

class SalesConversation(Base):
    __tablename__ = "sales_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    contact_wa_id = Column(String(20), ForeignKey("contacts.wa_id"), nullable=False, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)

    stage = Column(String(50), default="greeting")

    interests = Column(JSON, default=list)
    objections = Column(JSON, default=list)
    preferences = Column(JSON, default=dict)

    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)

    messages_count = Column(Integer, default=0)
    started_at = Column(DateTime, server_default=func.now())
    converted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
