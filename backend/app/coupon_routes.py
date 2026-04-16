"""
VendaFlow — Coupon Routes
CRUD de cupons + validação no checkout.
"""
from typing import Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models import Coupon
from app.auth import get_current_user, get_tenant_id

router = APIRouter(prefix="/api/coupons", tags=["coupons"])


class CouponCreate(BaseModel):
    code: str
    discount_type: str = "percentage"
    discount_value: Decimal
    min_order_value: Optional[Decimal] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = True
    expires_at: Optional[datetime] = None


class CouponUpdate(BaseModel):
    code: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None
    min_order_value: Optional[Decimal] = None
    max_uses: Optional[int] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class CouponValidate(BaseModel):
    code: str
    order_value: Decimal


def _serialize(c: Coupon) -> dict:
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "code": c.code,
        "discount_type": c.discount_type,
        "discount_value": str(c.discount_value) if c.discount_value is not None else None,
        "min_order_value": str(c.min_order_value) if c.min_order_value is not None else None,
        "max_uses": c.max_uses,
        "used_count": c.used_count,
        "is_active": c.is_active,
        "expires_at": c.expires_at.isoformat() if c.expires_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("")
async def list_coupons(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Coupon)
        .where(Coupon.tenant_id == tenant_id)
        .order_by(Coupon.created_at.desc())
    )
    return [_serialize(c) for c in result.scalars().all()]


@router.post("")
async def create_coupon(
    payload: CouponCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    if payload.discount_type not in ("percentage", "fixed"):
        raise HTTPException(status_code=400, detail="discount_type deve ser 'percentage' ou 'fixed'")

    data = payload.dict(exclude_unset=True)
    data["code"] = payload.code.upper().strip()

    coupon = Coupon(tenant_id=tenant_id, **data)
    db.add(coupon)
    await db.commit()
    await db.refresh(coupon)
    return _serialize(coupon)


@router.patch("/{coupon_id}")
async def update_coupon(
    coupon_id: int,
    payload: CouponUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Coupon).where(Coupon.id == coupon_id, Coupon.tenant_id == tenant_id)
    )
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="Cupom não encontrado")

    updates = payload.dict(exclude_unset=True)
    if "discount_type" in updates and updates["discount_type"] not in ("percentage", "fixed"):
        raise HTTPException(status_code=400, detail="discount_type deve ser 'percentage' ou 'fixed'")
    if "code" in updates and updates["code"]:
        updates["code"] = updates["code"].upper().strip()

    for field, value in updates.items():
        setattr(coupon, field, value)

    await db.commit()
    await db.refresh(coupon)
    return _serialize(coupon)


@router.delete("/{coupon_id}")
async def delete_coupon(
    coupon_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Coupon).where(Coupon.id == coupon_id, Coupon.tenant_id == tenant_id)
    )
    coupon = result.scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="Cupom não encontrado")

    await db.delete(coupon)
    await db.commit()
    return {"status": "deleted", "id": coupon_id}


@router.post("/validate")
async def validate_coupon(
    payload: CouponValidate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    code = payload.code.upper().strip()
    result = await db.execute(
        select(Coupon).where(Coupon.code == code, Coupon.tenant_id == tenant_id)
    )
    coupon = result.scalar_one_or_none()

    if not coupon:
        raise HTTPException(status_code=404, detail="Cupom não encontrado")

    if not coupon.is_active:
        raise HTTPException(status_code=400, detail="Cupom inativo")

    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Cupom expirado")

    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        raise HTTPException(status_code=400, detail="Limite de uso do cupom atingido")

    order_value = Decimal(payload.order_value)
    if coupon.min_order_value is not None and order_value < coupon.min_order_value:
        raise HTTPException(
            status_code=400,
            detail=f"Valor mínimo do pedido: {coupon.min_order_value}",
        )

    value = Decimal(coupon.discount_value)
    if coupon.discount_type == "percentage":
        discount = (order_value * value / Decimal(100)).quantize(Decimal("0.01"))
    else:
        discount = value

    if discount > order_value:
        discount = order_value

    final_value = order_value - discount

    return {
        "valid": True,
        "code": coupon.code,
        "discount_type": coupon.discount_type,
        "discount_value": str(value),
        "discount_amount": str(discount),
        "order_value": str(order_value),
        "final_value": str(final_value),
    }
