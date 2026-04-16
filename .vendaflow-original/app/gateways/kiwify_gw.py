"""
VendaFlow AI — Kiwify Payment Gateway
Gera links de checkout do Kiwify e processa webhooks.
"""
import httpx
import hmac
import hashlib
from decimal import Decimal
from urllib.parse import urlencode
from app.gateways import PaymentGatewayBase, PaymentLinkRequest, PaymentLinkResult

KIWIFY_API_BASE = "https://api.kiwify.com.br"


class KiwifyGateway(PaymentGatewayBase):
    
    def __init__(self, api_key: str, webhook_secret: str = None):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
    
    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        """
        Gera link de checkout do Kiwify.
        
        Kiwify funciona similar ao Hotmart: cada produto tem seu checkout.
        O external_product_id é o slug/ID do produto no Kiwify.
        """
        try:
            metadata = request.metadata or {}
            product_slug = metadata.get("external_product_id", "")
            
            if not product_slug:
                return PaymentLinkResult(
                    success=False,
                    gateway="kiwify",
                    error="Product slug do Kiwify não configurado no produto.",
                )
            
            # Montar URL de checkout do Kiwify
            base_url = f"https://pay.kiwify.com.br/{product_slug}"
            
            params = {
                "name": request.customer_name,
                "phone": request.customer_phone,
                "utm_source": "vendaflow_ai",
                "utm_medium": "whatsapp",
                "utm_campaign": request.order_number,
            }
            
            if request.customer_email:
                params["email"] = request.customer_email
            
            params = {k: v for k, v in params.items() if v}
            checkout_url = f"{base_url}?{urlencode(params)}"
            
            return PaymentLinkResult(
                success=True,
                gateway="kiwify",
                payment_url=checkout_url,
                payment_link_id=f"kiwify_{request.order_number}",
            )
        
        except Exception as e:
            return PaymentLinkResult(
                success=False,
                gateway="kiwify",
                error=f"Erro ao gerar link Kiwify: {str(e)}",
            )
    
    async def verify_payment(self, payment_id: str) -> dict:
        """Verifica status de pagamento no Kiwify."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{KIWIFY_API_BASE}/v1/orders/{payment_id}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=15,
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "status": data.get("status", "unknown"),
                        "amount_total": data.get("amount"),
                    }
                
                return {"status": "not_found"}
        
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def parse_webhook(self, payload: dict, headers: dict) -> dict:
        """
        Processa webhook do Kiwify.
        
        Kiwify envia POST com JSON.
        Eventos: order_approved, order_refunded, subscription_canceled, etc.
        """
        try:
            # Verificar assinatura
            if self.webhook_secret:
                received_sig = headers.get("x-kiwify-signature", "")
                import json as _json
                computed = hmac.new(
                    self.webhook_secret.encode(),
                    _json.dumps(payload, separators=(",", ":")).encode(),
                    hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(received_sig, computed):
                    return {"gateway": "kiwify", "error": "Assinatura inválida", "event_type": "error"}
            
            event_type = payload.get("webhook_event_type", payload.get("event", ""))
            order = payload.get("order", payload)
            customer = payload.get("Customer", payload.get("customer", {}))
            product = payload.get("Product", payload.get("product", {}))
            
            status_map = {
                "order_approved": "approved",
                "order_completed": "approved",
                "order_refunded": "refunded",
                "order_canceled": "refused",
                "subscription_canceled": "cancelled",
                "order_chargedback": "refunded",
            }
            
            return {
                "gateway": "kiwify",
                "event_type": event_type,
                "payment_status": status_map.get(event_type, "unknown"),
                "order_id": order.get("order_id"),
                "order_number": order.get("order_ref") or order.get("order_id"),
                "amount": order.get("charges", {}).get("brl") if isinstance(order.get("charges"), dict) else None,
                "customer_email": customer.get("email"),
                "customer_name": customer.get("full_name") or customer.get("name"),
                "customer_phone": customer.get("mobile") or customer.get("phone"),
                "product_name": product.get("name"),
                "gateway_event_id": order.get("order_id"),
                "raw": payload,
            }
        
        except Exception as e:
            return {"gateway": "kiwify", "error": str(e), "event_type": "error"}
