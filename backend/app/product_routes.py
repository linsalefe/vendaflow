"""
VendaFlow — Product Routes
CRUD para categorias, produtos e variantes (tenant-scoped).
"""
import re
from typing import Optional, List, Any
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, case
from pydantic import BaseModel

from app.database import get_db
from app.models import Product, ProductCategory, ProductVariant, User
from app.auth import get_current_user, get_tenant_id

router = APIRouter(prefix="/api/products", tags=["products"])


# ── Schemas ───────────────────────────────────────────────────────────────
class CategoryCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class ProductCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    product_type: Optional[str] = "physical"
    price: Decimal
    wholesale_price: Optional[Decimal] = None
    wholesale_min_qty: Optional[int] = None
    compare_at_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    category_id: Optional[int] = None
    track_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    low_stock_alert: Optional[int] = None
    weight_grams: Optional[int] = None
    digital_file_url: Optional[str] = None
    digital_access_days: Optional[int] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = None
    gateway_override: Optional[str] = None
    external_product_id: Optional[str] = None
    external_offer_id: Optional[str] = None
    has_variants: Optional[bool] = None
    variant_options: Optional[list] = None
    ai_selling_points: Optional[str] = None
    ai_objection_responses: Optional[dict] = None
    search_tags: Optional[List[str]] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    product_type: Optional[str] = None
    price: Optional[Decimal] = None
    wholesale_price: Optional[Decimal] = None
    wholesale_min_qty: Optional[int] = None
    compare_at_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    category_id: Optional[int] = None
    track_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    low_stock_alert: Optional[int] = None
    weight_grams: Optional[int] = None
    digital_file_url: Optional[str] = None
    digital_access_days: Optional[int] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = None
    gateway_override: Optional[str] = None
    external_product_id: Optional[str] = None
    external_offer_id: Optional[str] = None
    has_variants: Optional[bool] = None
    variant_options: Optional[list] = None
    ai_selling_points: Optional[str] = None
    ai_objection_responses: Optional[dict] = None
    search_tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None


class VariantCreate(BaseModel):
    variant_label: str
    variant_options: Optional[dict] = None
    sku: Optional[str] = None
    price_override: Optional[Decimal] = None
    stock_quantity: Optional[int] = None
    image_url: Optional[str] = None


class VariantUpdate(BaseModel):
    variant_label: Optional[str] = None
    variant_options: Optional[dict] = None
    sku: Optional[str] = None
    price_override: Optional[Decimal] = None
    stock_quantity: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


# ── Helpers ───────────────────────────────────────────────────────────────
def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _serialize_category(c: ProductCategory) -> dict:
    return {
        "id": c.id,
        "tenant_id": c.tenant_id,
        "name": c.name,
        "slug": c.slug,
        "description": c.description,
        "image_url": c.image_url,
        "parent_id": c.parent_id,
        "sort_order": c.sort_order,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _serialize_variant(v: ProductVariant) -> dict:
    return {
        "id": v.id,
        "product_id": v.product_id,
        "sku": v.sku,
        "variant_label": v.variant_label,
        "variant_options": v.variant_options,
        "price_override": str(v.price_override) if v.price_override is not None else None,
        "stock_quantity": v.stock_quantity,
        "image_url": v.image_url,
        "is_active": v.is_active,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _serialize_product(p: Product, variants: Optional[List[ProductVariant]] = None) -> dict:
    data = {
        "id": p.id,
        "tenant_id": p.tenant_id,
        "category_id": p.category_id,
        "name": p.name,
        "slug": p.slug,
        "description": p.description,
        "short_description": p.short_description,
        "product_type": p.product_type,
        "price": str(p.price) if p.price is not None else None,
        "wholesale_price": str(p.wholesale_price) if p.wholesale_price is not None else None,
        "wholesale_min_qty": p.wholesale_min_qty,
        "compare_at_price": str(p.compare_at_price) if p.compare_at_price is not None else None,
        "cost_price": str(p.cost_price) if p.cost_price is not None else None,
        "track_stock": p.track_stock,
        "stock_quantity": p.stock_quantity,
        "low_stock_alert": p.low_stock_alert,
        "weight_grams": p.weight_grams,
        "digital_file_url": p.digital_file_url,
        "digital_access_days": p.digital_access_days,
        "image_url": p.image_url,
        "images": p.images or [],
        "gateway_override": p.gateway_override,
        "external_product_id": p.external_product_id,
        "external_offer_id": p.external_offer_id,
        "has_variants": p.has_variants,
        "variant_options": p.variant_options,
        "ai_selling_points": p.ai_selling_points,
        "ai_objection_responses": p.ai_objection_responses,
        "search_tags": p.search_tags or [],
        "is_active": p.is_active,
        "is_featured": p.is_featured,
        "sort_order": p.sort_order,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    if variants is not None:
        data["variants"] = [_serialize_variant(v) for v in variants]
    return data


def _apply_updates(obj: Any, payload: BaseModel, exclude: set = None) -> None:
    exclude = exclude or set()
    for field, value in payload.dict(exclude_unset=True).items():
        if field in exclude:
            continue
        setattr(obj, field, value)


# ── Categorias ────────────────────────────────────────────────────────────
@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(ProductCategory)
        .where(ProductCategory.tenant_id == tenant_id)
        .order_by(ProductCategory.sort_order, ProductCategory.name)
    )
    return [_serialize_category(c) for c in result.scalars().all()]


@router.post("/categories")
async def create_category(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    slug = payload.slug or _slugify(payload.name)
    cat = ProductCategory(
        tenant_id=tenant_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        image_url=payload.image_url,
        parent_id=payload.parent_id,
        sort_order=payload.sort_order or 0,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return _serialize_category(cat)


@router.patch("/categories/{category_id}")
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(ProductCategory).where(
            ProductCategory.id == category_id,
            ProductCategory.tenant_id == tenant_id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    _apply_updates(cat, payload)
    await db.commit()
    await db.refresh(cat)
    return _serialize_category(cat)


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(ProductCategory).where(
            ProductCategory.id == category_id,
            ProductCategory.tenant_id == tenant_id,
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    await db.delete(cat)
    await db.commit()
    return {"status": "deleted"}


# ── Stats (antes de /{id} para não colidir) ───────────────────────────────
@router.get("/stats")
async def product_stats(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    total_result = await db.execute(
        select(func.count(Product.id)).where(Product.tenant_id == tenant_id)
    )
    active_result = await db.execute(
        select(func.count(Product.id)).where(
            Product.tenant_id == tenant_id, Product.is_active == True
        )
    )
    out_of_stock_result = await db.execute(
        select(func.count(Product.id)).where(
            Product.tenant_id == tenant_id,
            Product.track_stock == True,
            Product.stock_quantity <= 0,
        )
    )
    stock_units_result = await db.execute(
        select(func.coalesce(func.sum(Product.stock_quantity), 0)).where(
            Product.tenant_id == tenant_id,
            Product.track_stock == True,
        )
    )
    stock_value_result = await db.execute(
        select(
            func.coalesce(func.sum(Product.price * Product.stock_quantity), 0)
        ).where(
            Product.tenant_id == tenant_id,
            Product.track_stock == True,
        )
    )

    return {
        "total": total_result.scalar() or 0,
        "active": active_result.scalar() or 0,
        "out_of_stock": out_of_stock_result.scalar() or 0,
        "stock_units": int(stock_units_result.scalar() or 0),
        "stock_value": str(stock_value_result.scalar() or 0),
    }


# ── Produtos ──────────────────────────────────────────────────────────────
@router.get("")
async def list_products(
    category_id: Optional[int] = None,
    product_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    stmt = select(Product).where(Product.tenant_id == tenant_id)

    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if product_type:
        stmt = stmt.where(Product.product_type == product_type)
    if is_active is not None:
        stmt = stmt.where(Product.is_active == is_active)
    if search:
        term = f"%{search}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(term),
                Product.short_description.ilike(term),
                Product.search_tags.cast(str).ilike(term),
            )
        )

    stmt = stmt.order_by(Product.is_featured.desc(), Product.sort_order, Product.name)
    result = await db.execute(stmt)
    products = result.scalars().all()

    if not products:
        return []

    product_ids = [p.id for p in products]
    var_result = await db.execute(
        select(ProductVariant).where(ProductVariant.product_id.in_(product_ids))
    )
    variants_by_product: dict = {}
    for v in var_result.scalars().all():
        variants_by_product.setdefault(v.product_id, []).append(v)

    return [_serialize_product(p, variants_by_product.get(p.id, [])) for p in products]


@router.get("/{product_id}")
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.tenant_id == tenant_id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    var_result = await db.execute(
        select(ProductVariant).where(ProductVariant.product_id == product_id)
    )
    variants = var_result.scalars().all()
    return _serialize_product(product, list(variants))


@router.post("")
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    data = payload.dict(exclude_unset=True)
    data["slug"] = data.get("slug") or _slugify(payload.name)
    product = Product(tenant_id=tenant_id, **data)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return _serialize_product(product, [])


@router.patch("/{product_id}")
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.tenant_id == tenant_id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    _apply_updates(product, payload)
    await db.commit()
    await db.refresh(product)

    var_result = await db.execute(
        select(ProductVariant).where(ProductVariant.product_id == product_id)
    )
    return _serialize_product(product, list(var_result.scalars().all()))


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.tenant_id == tenant_id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    product.is_active = False
    await db.commit()
    return {"status": "deleted", "id": product_id}


# ── Variantes ─────────────────────────────────────────────────────────────
@router.post("/{product_id}/variants")
async def create_variant(
    product_id: int,
    payload: VariantCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.tenant_id == tenant_id
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    variant = ProductVariant(product_id=product_id, **payload.dict(exclude_unset=True))
    db.add(variant)

    if not product.has_variants:
        product.has_variants = True

    await db.commit()
    await db.refresh(variant)
    return _serialize_variant(variant)


@router.patch("/variants/{variant_id}")
async def update_variant(
    variant_id: int,
    payload: VariantUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(ProductVariant)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(
            ProductVariant.id == variant_id,
            Product.tenant_id == tenant_id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variante não encontrada")

    _apply_updates(variant, payload)
    await db.commit()
    await db.refresh(variant)
    return _serialize_variant(variant)


@router.delete("/variants/{variant_id}")
async def delete_variant(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    result = await db.execute(
        select(ProductVariant)
        .join(Product, Product.id == ProductVariant.product_id)
        .where(
            ProductVariant.id == variant_id,
            Product.tenant_id == tenant_id,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=404, detail="Variante não encontrada")

    await db.delete(variant)
    await db.commit()
    return {"status": "deleted", "id": variant_id}
