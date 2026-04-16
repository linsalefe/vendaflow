"""
VendaFlow AI — Payment Webhook Routes
Recebe webhooks do Stripe, Hotmart e Kiwify.
Atualiza pedido, notifica cliente via WhatsApp, entrega produto digital.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models import (
    Tenant, Order, Contact, PaymentEvent, SalesConversation
)
from app.gateways.stripe_gw import StripeGateway
from app.gateways.hotmart_gw import HotmartGateway
from app.gateways.kiwify_gw import KiwifyGateway

router = APIRouter(prefix="/webhooks", tags=["Payment Webhooks"])

SP_TZ = timezone(timedelta(hours=-3))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def _process_payment_event(
    gateway_data: dict,
    tenant: Tenant,
    db: AsyncSession,
) -> dict:
    """
    Processamento unificado de evento de pagamento.
    Funciona para qualquer gateway.
    """
    payment_status = gateway_data.get("payment_status", "unknown")
    order_number = gateway_data.get("order_number") or gateway_data.get("order_id")
    
    if not order_number:
        return {"status": "ignored", "reason": "No order reference"}
    
    # Buscar pedido
    order_result = await db.execute(
        select(Order).where(
            Order.tenant_id == tenant.id,
            Order.order_number == str(order_number),
        )
    )
    order = order_result.scalar_one_or_none()
    
    # Tentar pelo payment_link_id
    if not order and gateway_data.get("gateway_event_id"):
        order_result = await db.execute(
            select(Order).where(
                Order.tenant_id == tenant.id,
                Order.payment_link_id == gateway_data["gateway_event_id"],
            )
        )
        order = order_result.scalar_one_or_none()
    
    if not order:
        return {"status": "ignored", "reason": f"Order {order_number} not found"}
    
    # Salvar evento
    event = PaymentEvent(
        tenant_id=tenant.id,
        order_id=order.id,
        gateway=gateway_data.get("gateway", "unknown"),
        event_type=gateway_data.get("event_type", "unknown"),
        gateway_event_id=gateway_data.get("gateway_event_id"),
        payload=gateway_data.get("raw"),
        processed=True,
    )
    db.add(event)
    
    # Atualizar pedido
    if payment_status == "approved":
        order.payment_status = "approved"
        order.status = "paid"
        order.paid_at = datetime.now(SP_TZ).replace(tzinfo=None)
        
        # Atualizar contato
        contact_result = await db.execute(
            select(Contact).where(
                Contact.wa_id == order.contact_wa_id,
                Contact.tenant_id == tenant.id,
            )
        )
        contact = contact_result.scalar_one_or_none()
        if contact:
            contact.lead_status = "pago"
            contact.total_orders = (contact.total_orders or 0) + 1
            contact.total_spent = (contact.total_spent or 0) + order.total
            contact.last_order_at = datetime.now(SP_TZ).replace(tzinfo=None)
        
        # Atualizar sales conversation
        conv_result = await db.execute(
            select(SalesConversation).where(
                SalesConversation.order_id == order.id,
            )
        )
        conv = conv_result.scalar_one_or_none()
        if conv:
            conv.stage = "paid"
            conv.converted_at = datetime.now(SP_TZ).replace(tzinfo=None)
        
        # Se produto digital, marcar para entrega
        if order.digital_access_url:
            order.digital_access_sent = True
        
        # TODO: Enviar mensagem de confirmação via WhatsApp
        # await send_payment_confirmation(order, contact, tenant)
        
    elif payment_status == "refused":
        order.payment_status = "refused"
        # TODO: Enviar mensagem de falha e novo link
        
    elif payment_status == "refunded":
        order.payment_status = "refunded"
        order.status = "refunded"
        
    elif payment_status == "expired":
        order.payment_status = "expired"
        # TODO: Enviar lembrete com novo link
    
    # Atualizar email do contato se veio no webhook
    customer_email = gateway_data.get("customer_email")
    if customer_email:
        contact_result = await db.execute(
            select(Contact).where(
                Contact.wa_id == order.contact_wa_id,
                Contact.tenant_id == tenant.id,
            )
        )
        contact = contact_result.scalar_one_or_none()
        if contact and not contact.email:
            contact.email = customer_email
    
    await db.commit()
    
    return {
        "status": "processed",
        "order_number": order.order_number,
        "payment_status": payment_status,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STRIPE WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/stripe/{tenant_slug}")
async def stripe_webhook(
    tenant_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook do Stripe.
    URL: POST /webhooks/stripe/{tenant_slug}
    """
    # Buscar tenant
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.slug == tenant_slug)
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    
    if not tenant.stripe_secret_key:
        raise HTTPException(400, "Stripe not configured")
    
    # Parse webhook
    body = await request.body()
    headers = dict(request.headers)
    
    gateway = StripeGateway(
        secret_key=tenant.stripe_secret_key,
        webhook_secret=tenant.stripe_webhook_secret,
    )
    gateway_data = gateway.parse_webhook(body, headers)
    
    if gateway_data.get("error"):
        print(f"⚠️ Stripe webhook error: {gateway_data['error']}")
        raise HTTPException(400, gateway_data["error"])
    
    # Mapear order_id do metadata
    if not gateway_data.get("order_number"):
        gateway_data["order_number"] = gateway_data.get("order_id")
    
    result = await _process_payment_event(gateway_data, tenant, db)
    
    print(f"💳 Stripe webhook [{tenant_slug}]: {gateway_data.get('event_type')} → {result.get('status')}")
    
    return {"received": True, **result}


# ─────────────────────────────────────────────────────────────────────────────
# HOTMART WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/hotmart/{tenant_slug}")
async def hotmart_webhook(
    tenant_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook do Hotmart (Hottok).
    URL: POST /webhooks/hotmart/{tenant_slug}
    """
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.slug == tenant_slug)
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    
    if not tenant.hotmart_token:
        raise HTTPException(400, "Hotmart not configured")
    
    payload = await request.json()
    headers = dict(request.headers)
    
    gateway = HotmartGateway(
        token=tenant.hotmart_token,
        hottok=tenant.hotmart_hottok,
    )
    gateway_data = gateway.parse_webhook(payload, headers)
    
    if gateway_data.get("error"):
        print(f"⚠️ Hotmart webhook error: {gateway_data['error']}")
        raise HTTPException(400, gateway_data["error"])
    
    result = await _process_payment_event(gateway_data, tenant, db)
    
    print(f"🔥 Hotmart webhook [{tenant_slug}]: {gateway_data.get('event_type')} → {result.get('status')}")
    
    return {"received": True, **result}


# ─────────────────────────────────────────────────────────────────────────────
# KIWIFY WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/kiwify/{tenant_slug}")
async def kiwify_webhook(
    tenant_slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook do Kiwify.
    URL: POST /webhooks/kiwify/{tenant_slug}
    """
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.slug == tenant_slug)
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    
    if not tenant.kiwify_api_key:
        raise HTTPException(400, "Kiwify not configured")
    
    payload = await request.json()
    headers = dict(request.headers)
    
    gateway = KiwifyGateway(
        api_key=tenant.kiwify_api_key,
        webhook_secret=tenant.kiwify_webhook_secret,
    )
    gateway_data = gateway.parse_webhook(payload, headers)
    
    if gateway_data.get("error"):
        print(f"⚠️ Kiwify webhook error: {gateway_data['error']}")
        raise HTTPException(400, gateway_data["error"])
    
    result = await _process_payment_event(gateway_data, tenant, db)
    
    print(f"🥝 Kiwify webhook [{tenant_slug}]: {gateway_data.get('event_type')} → {result.get('status')}")
    
    return {"received": True, **result}
