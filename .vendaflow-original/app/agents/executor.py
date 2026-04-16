"""
VendaFlow AI — Sales Agent Tool Executor
Executa as tools chamadas pelo GPT durante a conversa de vendas.
"""
import json
import random
import string
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from app.models import (
    Product, ProductVariant, ProductCategory, CartItem, Order, OrderItem,
    Contact, Tenant, Coupon, SalesConversation, PaymentEvent
)
from app.gateways.factory import get_gateway
from app.gateways import PaymentLinkRequest

SP_TZ = timezone(timedelta(hours=-3))


def _generate_order_number() -> str:
    """Gera número de pedido: VF-XXXXXX"""
    chars = string.ascii_uppercase + string.digits
    code = ''.join(random.choices(chars, k=6))
    return f"VF-{code}"


async def execute_tool(
    tool_name: str,
    args: dict,
    wa_id: str,
    tenant_id: int,
    db: AsyncSession,
) -> str:
    """Executa uma tool e retorna o resultado como string para o GPT."""
    
    try:
        if tool_name == "search_products":
            return await _search_products(args, tenant_id, db)
        
        elif tool_name == "get_product_details":
            return await _get_product_details(args, tenant_id, db)
        
        elif tool_name == "check_stock":
            return await _check_stock(args, tenant_id, db)
        
        elif tool_name == "add_to_cart":
            return await _add_to_cart(args, wa_id, tenant_id, db)
        
        elif tool_name == "view_cart":
            return await _view_cart(wa_id, tenant_id, db)
        
        elif tool_name == "remove_from_cart":
            return await _remove_from_cart(args, wa_id, db)
        
        elif tool_name == "update_cart_quantity":
            return await _update_cart_quantity(args, wa_id, db)
        
        elif tool_name == "apply_coupon":
            return await _apply_coupon(args, tenant_id, db)
        
        elif tool_name == "create_order_and_payment_link":
            return await _create_order_and_payment_link(args, wa_id, tenant_id, db)
        
        elif tool_name == "check_order_status":
            return await _check_order_status(args, tenant_id, db)
        
        elif tool_name == "collect_customer_data":
            return await _collect_customer_data(args, wa_id, db)
        
        elif tool_name == "move_pipeline":
            return await _move_pipeline(args, wa_id, db)
        
        elif tool_name == "get_upsell_suggestions":
            return await _get_upsell_suggestions(args, tenant_id, db)
        
        else:
            return json.dumps({"error": f"Tool '{tool_name}' não reconhecida."})
    
    except Exception as e:
        return json.dumps({"error": f"Erro ao executar {tool_name}: {str(e)}"})


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGO
# ─────────────────────────────────────────────────────────────────────────────

async def _search_products(args: dict, tenant_id: int, db: AsyncSession) -> str:
    query = args.get("query", "").lower()
    category = args.get("category", "")
    max_results = args.get("max_results", 5)
    
    stmt = select(Product).where(
        Product.tenant_id == tenant_id,
        Product.is_active == True,
    )
    
    # Busca por nome, descrição ou tags
    if query:
        stmt = stmt.where(
            or_(
                Product.name.ilike(f"%{query}%"),
                Product.short_description.ilike(f"%{query}%"),
                Product.search_tags.cast(str).ilike(f"%{query}%"),
            )
        )
    
    if category:
        stmt = stmt.join(ProductCategory).where(
            ProductCategory.slug.ilike(f"%{category}%")
        )
    
    stmt = stmt.order_by(Product.is_featured.desc(), Product.sort_order).limit(max_results)
    result = await db.execute(stmt)
    products = result.scalars().all()
    
    if not products:
        return json.dumps({"products": [], "message": "Nenhum produto encontrado."})
    
    items = []
    for p in products:
        item = {
            "id": p.id,
            "name": p.name,
            "price": str(p.price),
            "type": p.product_type,
            "short_description": p.short_description or "",
            "image_url": p.image_url or "",
            "in_stock": p.stock_quantity > 0 if p.track_stock else True,
        }
        if p.compare_at_price:
            item["compare_at_price"] = str(p.compare_at_price)
        if p.wholesale_price:
            item["wholesale_price"] = str(p.wholesale_price)
            item["wholesale_min_qty"] = p.wholesale_min_qty
        if p.has_variants:
            item["has_variants"] = True
            item["variant_options"] = p.variant_options
        items.append(item)
    
    return json.dumps({"products": items, "count": len(items)}, ensure_ascii=False)


async def _get_product_details(args: dict, tenant_id: int, db: AsyncSession) -> str:
    product_id = args.get("product_id")
    
    result = await db.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == tenant_id,
        )
    )
    product = result.scalar_one_or_none()
    
    if not product:
        return json.dumps({"error": "Produto não encontrado."})
    
    details = {
        "id": product.id,
        "name": product.name,
        "description": product.description or product.short_description or "",
        "price": str(product.price),
        "type": product.product_type,
        "image_url": product.image_url,
        "images": product.images or [],
        "in_stock": product.stock_quantity > 0 if product.track_stock else True,
        "stock_quantity": product.stock_quantity if product.track_stock else "ilimitado",
        "ai_selling_points": product.ai_selling_points or "",
    }
    
    if product.compare_at_price:
        details["compare_at_price"] = str(product.compare_at_price)
        discount_pct = round((1 - float(product.price) / float(product.compare_at_price)) * 100)
        details["discount_percentage"] = f"{discount_pct}%"
    
    if product.wholesale_price:
        details["wholesale_price"] = str(product.wholesale_price)
        details["wholesale_min_qty"] = product.wholesale_min_qty
    
    if product.has_variants:
        var_result = await db.execute(
            select(ProductVariant).where(
                ProductVariant.product_id == product_id,
                ProductVariant.is_active == True,
            )
        )
        variants = var_result.scalars().all()
        details["variants"] = [
            {
                "id": v.id,
                "label": v.variant_label,
                "options": v.variant_options,
                "price": str(v.price_override) if v.price_override else str(product.price),
                "stock": v.stock_quantity,
            }
            for v in variants
        ]
    
    if product.ai_objection_responses:
        details["objection_responses"] = product.ai_objection_responses
    
    return json.dumps(details, ensure_ascii=False)


async def _check_stock(args: dict, tenant_id: int, db: AsyncSession) -> str:
    product_id = args.get("product_id")
    variant_id = args.get("variant_id")
    quantity = args.get("quantity", 1)
    
    if variant_id:
        result = await db.execute(
            select(ProductVariant).where(ProductVariant.id == variant_id)
        )
        variant = result.scalar_one_or_none()
        if variant:
            available = variant.stock_quantity >= quantity
            return json.dumps({
                "available": available,
                "stock": variant.stock_quantity,
                "requested": quantity,
            })
    
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        return json.dumps({"error": "Produto não encontrado."})
    
    if not product.track_stock:
        return json.dumps({"available": True, "stock": "ilimitado", "requested": quantity})
    
    available = product.stock_quantity >= quantity
    return json.dumps({
        "available": available,
        "stock": product.stock_quantity,
        "requested": quantity,
    })


# ─────────────────────────────────────────────────────────────────────────────
# CARRINHO
# ─────────────────────────────────────────────────────────────────────────────

async def _add_to_cart(args: dict, wa_id: str, tenant_id: int, db: AsyncSession) -> str:
    product_id = args.get("product_id")
    variant_id = args.get("variant_id")
    quantity = args.get("quantity", 1)
    
    # Buscar produto
    result = await db.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        return json.dumps({"error": "Produto não encontrado."})
    
    # Determinar preço
    unit_price = product.price
    
    # Preço atacado se quantidade suficiente
    if product.wholesale_price and quantity >= (product.wholesale_min_qty or 6):
        unit_price = product.wholesale_price
    
    # Override de variante
    if variant_id:
        var_result = await db.execute(
            select(ProductVariant).where(ProductVariant.id == variant_id)
        )
        variant = var_result.scalar_one_or_none()
        if variant and variant.price_override:
            unit_price = variant.price_override
    
    # Verificar se já existe no carrinho
    existing = await db.execute(
        select(CartItem).where(
            CartItem.contact_wa_id == wa_id,
            CartItem.product_id == product_id,
            CartItem.variant_id == variant_id,
            CartItem.tenant_id == tenant_id,
        )
    )
    existing_item = existing.scalar_one_or_none()
    
    if existing_item:
        existing_item.quantity += quantity
        existing_item.unit_price = unit_price
    else:
        cart_item = CartItem(
            tenant_id=tenant_id,
            contact_wa_id=wa_id,
            product_id=product_id,
            variant_id=variant_id,
            quantity=quantity,
            unit_price=unit_price,
        )
        db.add(cart_item)
    
    await db.commit()
    
    is_wholesale = product.wholesale_price and quantity >= (product.wholesale_min_qty or 6)
    
    return json.dumps({
        "success": True,
        "product": product.name,
        "quantity": quantity,
        "unit_price": str(unit_price),
        "total_item": str(unit_price * quantity),
        "wholesale_applied": is_wholesale,
    }, ensure_ascii=False)


async def _view_cart(wa_id: str, tenant_id: int, db: AsyncSession) -> str:
    result = await db.execute(
        select(CartItem).where(
            CartItem.contact_wa_id == wa_id,
            CartItem.tenant_id == tenant_id,
        )
    )
    items = result.scalars().all()
    
    if not items:
        return json.dumps({"items": [], "total": "0.00", "message": "Carrinho vazio."})
    
    cart_items = []
    total = Decimal("0")
    
    for item in items:
        prod_result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = prod_result.scalar_one_or_none()
        
        variant_label = ""
        if item.variant_id:
            var_result = await db.execute(select(ProductVariant).where(ProductVariant.id == item.variant_id))
            variant = var_result.scalar_one_or_none()
            variant_label = variant.variant_label if variant else ""
        
        item_total = item.unit_price * item.quantity
        total += item_total
        
        cart_items.append({
            "cart_item_id": item.id,
            "product_id": item.product_id,
            "product_name": product.name if product else "Produto",
            "variant": variant_label,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
            "total": str(item_total),
        })
    
    return json.dumps({
        "items": cart_items,
        "items_count": len(cart_items),
        "total": str(total),
    }, ensure_ascii=False)


async def _remove_from_cart(args: dict, wa_id: str, db: AsyncSession) -> str:
    cart_item_id = args.get("cart_item_id")
    
    result = await db.execute(
        select(CartItem).where(
            CartItem.id == cart_item_id,
            CartItem.contact_wa_id == wa_id,
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        return json.dumps({"error": "Item não encontrado no carrinho."})
    
    await db.delete(item)
    await db.commit()
    
    return json.dumps({"success": True, "removed_id": cart_item_id})


async def _update_cart_quantity(args: dict, wa_id: str, db: AsyncSession) -> str:
    cart_item_id = args.get("cart_item_id")
    quantity = args.get("quantity", 1)
    
    result = await db.execute(
        select(CartItem).where(
            CartItem.id == cart_item_id,
            CartItem.contact_wa_id == wa_id,
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        return json.dumps({"error": "Item não encontrado no carrinho."})
    
    item.quantity = quantity
    await db.commit()
    
    return json.dumps({"success": True, "new_quantity": quantity})


# ─────────────────────────────────────────────────────────────────────────────
# CUPOM
# ─────────────────────────────────────────────────────────────────────────────

async def _apply_coupon(args: dict, tenant_id: int, db: AsyncSession) -> str:
    code = args.get("coupon_code", "").strip().upper()
    
    result = await db.execute(
        select(Coupon).where(
            Coupon.tenant_id == tenant_id,
            Coupon.code == code,
            Coupon.is_active == True,
        )
    )
    coupon = result.scalar_one_or_none()
    
    if not coupon:
        return json.dumps({"valid": False, "error": "Cupom não encontrado ou inativo."})
    
    now = datetime.now(SP_TZ)
    if coupon.expires_at and coupon.expires_at < now.replace(tzinfo=None):
        return json.dumps({"valid": False, "error": "Cupom expirado."})
    
    if coupon.max_uses and coupon.used_count >= coupon.max_uses:
        return json.dumps({"valid": False, "error": "Cupom esgotado."})
    
    return json.dumps({
        "valid": True,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": str(coupon.discount_value),
        "min_order_value": str(coupon.min_order_value) if coupon.min_order_value else None,
    }, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# PEDIDO + LINK DE PAGAMENTO (CORE)
# ─────────────────────────────────────────────────────────────────────────────

async def _create_order_and_payment_link(
    args: dict, wa_id: str, tenant_id: int, db: AsyncSession
) -> str:
    """
    CORE DA VENDA:
    1. Busca carrinho
    2. Cria pedido
    3. Aplica cupom (se houver)
    4. Gera link de pagamento no gateway
    5. Atualiza CRM
    """
    
    # 1. Buscar carrinho
    cart_result = await db.execute(
        select(CartItem).where(
            CartItem.contact_wa_id == wa_id,
            CartItem.tenant_id == tenant_id,
        )
    )
    cart_items = cart_result.scalars().all()
    
    if not cart_items:
        return json.dumps({"error": "Carrinho vazio. Adicione produtos primeiro."})
    
    # 2. Buscar tenant
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        return json.dumps({"error": "Tenant não encontrado."})
    
    # 3. Buscar contato
    contact_result = await db.execute(
        select(Contact).where(Contact.wa_id == wa_id, Contact.tenant_id == tenant_id)
    )
    contact = contact_result.scalar_one_or_none()
    
    # 4. Montar itens do pedido
    order_items = []
    subtotal = Decimal("0")
    first_product = None
    
    for ci in cart_items:
        prod_result = await db.execute(select(Product).where(Product.id == ci.product_id))
        product = prod_result.scalar_one_or_none()
        if not product:
            continue
        
        if not first_product:
            first_product = product
        
        variant_label = ""
        if ci.variant_id:
            var_result = await db.execute(select(ProductVariant).where(ProductVariant.id == ci.variant_id))
            variant = var_result.scalar_one_or_none()
            variant_label = variant.variant_label if variant else ""
        
        item_total = ci.unit_price * ci.quantity
        subtotal += item_total
        
        order_items.append({
            "product_id": ci.product_id,
            "variant_id": ci.variant_id,
            "product_name": product.name,
            "variant_label": variant_label,
            "quantity": ci.quantity,
            "unit_price": ci.unit_price,
            "total_price": item_total,
        })
    
    # 5. Aplicar cupom
    discount = Decimal("0")
    coupon_code = args.get("coupon_code")
    if coupon_code:
        coupon_result = await db.execute(
            select(Coupon).where(
                Coupon.tenant_id == tenant_id,
                Coupon.code == coupon_code.strip().upper(),
                Coupon.is_active == True,
            )
        )
        coupon = coupon_result.scalar_one_or_none()
        if coupon:
            if coupon.discount_type == "percentage":
                discount = subtotal * (coupon.discount_value / Decimal("100"))
            else:
                discount = coupon.discount_value
            coupon.used_count = (coupon.used_count or 0) + 1
    
    total = subtotal - discount
    if total < 0:
        total = Decimal("0")
    
    # 6. Criar pedido
    order_number = _generate_order_number()
    order = Order(
        tenant_id=tenant_id,
        contact_wa_id=wa_id,
        order_number=order_number,
        status="pending",
        subtotal=subtotal,
        discount_amount=discount,
        total=total,
        coupon_code=coupon_code,
        ai_generated=True,
    )
    db.add(order)
    await db.flush()  # para ter o order.id
    
    for oi in order_items:
        db.add(OrderItem(
            order_id=order.id,
            product_id=oi["product_id"],
            variant_id=oi["variant_id"],
            product_name=oi["product_name"],
            variant_label=oi["variant_label"],
            quantity=oi["quantity"],
            unit_price=oi["unit_price"],
            total_price=oi["total_price"],
        ))
    
    # 7. Gerar link de pagamento
    gateway = get_gateway(tenant, first_product)
    
    link_items = [
        {"name": oi["product_name"], "quantity": oi["quantity"], "unit_price": oi["unit_price"]}
        for oi in order_items
    ]
    
    link_request = PaymentLinkRequest(
        order_id=order.id,
        order_number=order_number,
        customer_name=contact.name if contact else "Cliente",
        customer_email=args.get("customer_email") or (contact.email if contact else None),
        customer_phone=wa_id,
        items=link_items,
        total=total,
        metadata={
            "external_product_id": first_product.external_product_id if first_product else None,
            "external_offer_id": first_product.external_offer_id if first_product else None,
        },
    )
    
    link_result = await gateway.create_payment_link(link_request)
    
    if not link_result.success:
        return json.dumps({
            "error": f"Erro ao gerar link de pagamento: {link_result.error}",
            "order_number": order_number,
        })
    
    # 8. Atualizar pedido com link
    order.payment_gateway = link_result.gateway
    order.payment_link = link_result.payment_url
    order.payment_link_id = link_result.payment_link_id
    
    # 9. Limpar carrinho
    for ci in cart_items:
        await db.delete(ci)
    
    # 10. Atualizar pipeline do contato
    if contact:
        contact.lead_status = "link_enviado"
    
    # 11. Atualizar sales conversation
    conv_result = await db.execute(
        select(SalesConversation).where(
            SalesConversation.contact_wa_id == wa_id,
            SalesConversation.tenant_id == tenant_id,
        ).order_by(SalesConversation.created_at.desc()).limit(1)
    )
    conversation = conv_result.scalar_one_or_none()
    if conversation:
        conversation.stage = "link_sent"
        conversation.order_id = order.id
    
    await db.commit()
    
    return json.dumps({
        "success": True,
        "order_number": order_number,
        "payment_url": link_result.payment_url,
        "gateway": link_result.gateway,
        "subtotal": str(subtotal),
        "discount": str(discount),
        "total": str(total),
        "items_count": len(order_items),
    }, ensure_ascii=False)


async def _check_order_status(args: dict, tenant_id: int, db: AsyncSession) -> str:
    order_number = args.get("order_number", "")
    
    result = await db.execute(
        select(Order).where(
            Order.order_number == order_number,
            Order.tenant_id == tenant_id,
        )
    )
    order = result.scalar_one_or_none()
    
    if not order:
        return json.dumps({"error": "Pedido não encontrado."})
    
    return json.dumps({
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "total": str(order.total),
        "tracking_code": order.tracking_code,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    })


# ─────────────────────────────────────────────────────────────────────────────
# CRM
# ─────────────────────────────────────────────────────────────────────────────

async def _collect_customer_data(args: dict, wa_id: str, db: AsyncSession) -> str:
    result = await db.execute(select(Contact).where(Contact.wa_id == wa_id))
    contact = result.scalar_one_or_none()
    
    if not contact:
        return json.dumps({"error": "Contato não encontrado."})
    
    updated = []
    if args.get("name"):
        contact.name = args["name"]; updated.append("name")
    if args.get("email"):
        contact.email = args["email"]; updated.append("email")
    if args.get("cpf"):
        contact.cpf = args["cpf"]; updated.append("cpf")
    if args.get("cep"):
        contact.address_cep = args["cep"]; updated.append("cep")
    if args.get("is_wholesale") is not None:
        contact.is_wholesale = args["is_wholesale"]; updated.append("is_wholesale")
    
    if args.get("preferences"):
        try:
            existing = json.loads(contact.notes or "{}")
        except (json.JSONDecodeError, TypeError):
            existing = {}
        existing.update(args["preferences"])
        contact.notes = json.dumps(existing, ensure_ascii=False)
        updated.append("preferences")
    
    await db.commit()
    
    return json.dumps({"success": True, "updated_fields": updated})


async def _move_pipeline(args: dict, wa_id: str, db: AsyncSession) -> str:
    target = args.get("target_stage", "novo")
    
    result = await db.execute(select(Contact).where(Contact.wa_id == wa_id))
    contact = result.scalar_one_or_none()
    
    if not contact:
        return json.dumps({"error": "Contato não encontrado."})
    
    old_status = contact.lead_status
    contact.lead_status = target
    await db.commit()
    
    return json.dumps({"success": True, "from": old_status, "to": target})


async def _get_upsell_suggestions(args: dict, tenant_id: int, db: AsyncSession) -> str:
    current_ids = args.get("current_product_ids", [])
    
    # Buscar produtos featured ou da mesma categoria
    result = await db.execute(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.is_active == True,
            Product.is_featured == True,
            ~Product.id.in_(current_ids) if current_ids else True,
        ).limit(3)
    )
    products = result.scalars().all()
    
    suggestions = [
        {
            "id": p.id,
            "name": p.name,
            "price": str(p.price),
            "short_description": p.short_description or "",
            "image_url": p.image_url or "",
        }
        for p in products
    ]
    
    return json.dumps({"suggestions": suggestions}, ensure_ascii=False)
