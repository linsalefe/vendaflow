"""
VendaFlow — Gateway Config Routes
Configuração dos gateways de pagamento do tenant (admin only).
Secrets são retornados mascarados (***últimos 4 chars).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models import Tenant, User
from app.auth import get_current_user, get_tenant_id

router = APIRouter(prefix="/api/gateways", tags=["gateways"])


GATEWAY_FIELDS = [
    "stripe_secret_key",
    "stripe_webhook_secret",
    "hotmart_token",
    "hotmart_hottok",
    "kiwify_api_key",
    "kiwify_webhook_secret",
    "mercadopago_access_token",
    "mercadopago_webhook_secret",
]

VALID_DEFAULT_GATEWAYS = {"stripe", "hotmart", "kiwify", "mercadopago"}


class GatewayConfig(BaseModel):
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    hotmart_token: Optional[str] = None
    hotmart_hottok: Optional[str] = None
    kiwify_api_key: Optional[str] = None
    kiwify_webhook_secret: Optional[str] = None
    mercadopago_access_token: Optional[str] = None
    mercadopago_webhook_secret: Optional[str] = None
    default_gateway: Optional[str] = None


class GatewayTestRequest(BaseModel):
    gateway: str


def _mask(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    tail = value[-4:] if len(value) >= 4 else value
    return f"***{tail}"


def _require_admin(user: User) -> None:
    if user.role not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem configurar gateways",
        )


async def _get_tenant(db: AsyncSession, tenant_id: int) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return tenant


@router.get("")
async def get_gateways(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    tenant = await _get_tenant(db, tenant_id)

    return {
        "default_gateway": tenant.default_gateway,
        "stripe_secret_key": _mask(tenant.stripe_secret_key),
        "stripe_webhook_secret": _mask(tenant.stripe_webhook_secret),
        "hotmart_token": _mask(tenant.hotmart_token),
        "hotmart_hottok": _mask(tenant.hotmart_hottok),
        "kiwify_api_key": _mask(tenant.kiwify_api_key),
        "kiwify_webhook_secret": _mask(tenant.kiwify_webhook_secret),
        "mercadopago_access_token": _mask(tenant.mercadopago_access_token),
        "mercadopago_webhook_secret": _mask(tenant.mercadopago_webhook_secret),
    }


@router.patch("")
async def update_gateways(
    payload: GatewayConfig,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    tenant = await _get_tenant(db, tenant_id)

    updates = payload.dict(exclude_unset=True)

    if "default_gateway" in updates and updates["default_gateway"] not in VALID_DEFAULT_GATEWAYS:
        raise HTTPException(
            status_code=400,
            detail=f"default_gateway deve ser um de: {sorted(VALID_DEFAULT_GATEWAYS)}",
        )

    for field, value in updates.items():
        if value is None:
            continue
        setattr(tenant, field, value)

    await db.commit()
    await db.refresh(tenant)

    return {
        "default_gateway": tenant.default_gateway,
        "stripe_secret_key": _mask(tenant.stripe_secret_key),
        "stripe_webhook_secret": _mask(tenant.stripe_webhook_secret),
        "hotmart_token": _mask(tenant.hotmart_token),
        "hotmart_hottok": _mask(tenant.hotmart_hottok),
        "kiwify_api_key": _mask(tenant.kiwify_api_key),
        "kiwify_webhook_secret": _mask(tenant.kiwify_webhook_secret),
        "mercadopago_access_token": _mask(tenant.mercadopago_access_token),
        "mercadopago_webhook_secret": _mask(tenant.mercadopago_webhook_secret),
    }


@router.post("/test")
async def test_gateway(
    payload: GatewayTestRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    tenant = await _get_tenant(db, tenant_id)
    gateway = payload.gateway.lower().strip()

    if gateway not in VALID_DEFAULT_GATEWAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Gateway inválido. Use um de: {sorted(VALID_DEFAULT_GATEWAYS)}",
        )

    try:
        if gateway == "stripe":
            if not tenant.stripe_secret_key:
                raise HTTPException(status_code=400, detail="stripe_secret_key não configurada")
            import stripe as stripe_lib
            stripe_lib.api_key = tenant.stripe_secret_key
            stripe_lib.Charge.list(limit=1)
            return {"ok": True, "gateway": "stripe", "message": "Conexão OK"}

        if gateway == "hotmart":
            if not tenant.hotmart_token:
                raise HTTPException(status_code=400, detail="hotmart_token não configurado")
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://developers.hotmart.com/payments/api/v1/sales/history",
                    headers={"Authorization": f"Bearer {tenant.hotmart_token}"},
                    params={"max_results": 1},
                )
            if resp.status_code >= 400:
                return {"ok": False, "gateway": "hotmart", "status": resp.status_code, "message": resp.text[:200]}
            return {"ok": True, "gateway": "hotmart", "message": "Conexão OK"}

        if gateway == "kiwify":
            if not tenant.kiwify_api_key:
                raise HTTPException(status_code=400, detail="kiwify_api_key não configurada")
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://public-api.kiwify.com/v1/products",
                    headers={"Authorization": f"Bearer {tenant.kiwify_api_key}"},
                )
            if resp.status_code >= 400:
                return {"ok": False, "gateway": "kiwify", "status": resp.status_code, "message": resp.text[:200]}
            return {"ok": True, "gateway": "kiwify", "message": "Conexão OK"}

        if gateway == "mercadopago":
            if not tenant.mercadopago_access_token:
                raise HTTPException(status_code=400, detail="mercadopago_access_token não configurado")
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.mercadopago.com/users/me",
                    headers={"Authorization": f"Bearer {tenant.mercadopago_access_token}"},
                )
            if resp.status_code >= 400:
                return {"ok": False, "gateway": "mercadopago", "status": resp.status_code, "message": resp.text[:200]}
            return {"ok": True, "gateway": "mercadopago", "message": "Conexão OK"}

    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "gateway": gateway, "message": f"Erro: {str(e)[:200]}"}

    raise HTTPException(status_code=400, detail="Gateway não implementado")
