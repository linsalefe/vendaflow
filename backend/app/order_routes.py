"""
VendaFlow — Order Routes
Leitura e gestão de pedidos. Criação é feita pela IA (sales_agent), não pelo painel.
"""
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.database import get_db
from app.models import Order, OrderItem
from app.auth import get_current_user, get_tenant_id

router = APIRouter(prefix="/api/orders", tags=["orders"])


REVENUE_STATUSES = ("paid", "processing", "shipped", "delivered")


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None
    tracking_code: Optional[str] = None
    notes: Optional[str] = None


def _serialize_item(item: OrderItem) -> dict:
    return {
        "id": item.id,
        "order_id": item.order_id,
        "product_id": item.product_id,
        "variant_id": item.variant_id,
        "product_name": item.product_name,
        "variant_label": item.variant_label,
        "quantity": item.quantity,
        "unit_price": str(item.unit_price) if item.unit_price is not None else None,
        "total_price": str(item.total_price) if item.total_price is not None else None,
    }


def _serialize_order(o: Order, items: Optional[List[OrderItem]] = None) -> dict:
    data = {
        "id": o.id,
        "tenant_id": o.tenant_id,
        "contact_wa_id": o.contact_wa_id,
        "order_number": o.order_number,
        "status": o.status,
        "subtotal": str(o.subtotal) if o.subtotal is not None else None,
        "discount_amount": str(o.discount_amount) if o.discount_amount is not None else None,
        "shipping_cost": str(o.shipping_cost) if o.shipping_cost is not None else None,
        "total": str(o.total) if o.total is not None else None,
        "payment_gateway": o.payment_gateway,
        "payment_link": o.payment_link,
        "payment_link_id": o.payment_link_id,
        "payment_status": o.payment_status,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "shipping_address": o.shipping_address,
        "tracking_code": o.tracking_code,
        "coupon_code": o.coupon_code,
        "digital_access_url": o.digital_access_url,
        "digital_access_sent": o.digital_access_sent,
        "notes": o.notes,
        "ai_generated": o.ai_generated,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }
    if items is not None:
        data["items"] = [_serialize_item(i) for i in items]
    return data


@router.get("/stats")
async def order_stats(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    total_result = await db.execute(
        select(func.count(Order.id)).where(Order.tenant_id == tenant_id)
    )
    total_orders = total_result.scalar() or 0

    revenue_result = await db.execute(
        select(func.coalesce(func.sum(Order.total), 0)).where(
            Order.tenant_id == tenant_id,
            Order.status.in_(REVENUE_STATUSES),
        )
    )
    revenue = revenue_result.scalar() or 0

    paid_count_result = await db.execute(
        select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id,
            Order.status.in_(REVENUE_STATUSES),
        )
    )
    paid_count = paid_count_result.scalar() or 0

    avg_ticket = (float(revenue) / paid_count) if paid_count else 0.0

    status_result = await db.execute(
        select(Order.status, func.count(Order.id))
        .where(Order.tenant_id == tenant_id)
        .group_by(Order.status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}

    return {
        "total_orders": total_orders,
        "revenue": str(revenue),
        "paid_orders": paid_count,
        "avg_ticket": round(avg_ticket, 2),
        "by_status": by_status,
    }


@router.get("")
async def list_orders(
    status: Optional[str] = None,
    payment_status: Optional[str] = None,
    contact_wa_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    stmt = select(Order).where(Order.tenant_id == tenant_id)

    if status:
        stmt = stmt.where(Order.status == status)
    if payment_status:
        stmt = stmt.where(Order.payment_status == payment_status)
    if contact_wa_id:
        stmt = stmt.where(Order.contact_wa_id == contact_wa_id)
    if date_from:
        stmt = stmt.where(Order.created_at >= date_from)
    if date_to:
        stmt = stmt.where(Order.created_at <= date_to)

    stmt = stmt.order_by(Order.created_at.desc())
    result = await db.execute(stmt)
    orders = result.scalars().all()

    if not orders:
        return []

    order_ids = [o.id for o in orders]
    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id.in_(order_ids))
    )
    items_by_order: dict = {}
    for item in items_result.scalars().all():
        items_by_order.setdefault(item.order_id, []).append(item)

    return [_serialize_order(o, items_by_order.get(o.id, [])) for o in orders]


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    return _serialize_order(order, list(items_result.scalars().all()))


@router.patch("/{order_id}")
async def update_order(
    order_id: int,
    payload: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    updates = payload.dict(exclude_unset=True)
    for field, value in updates.items():
        setattr(order, field, value)

    if updates.get("payment_status") == "approved" and order.paid_at is None:
        order.paid_at = datetime.utcnow()

    await db.commit()
    await db.refresh(order)

    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    return _serialize_order(order, list(items_result.scalars().all()))
