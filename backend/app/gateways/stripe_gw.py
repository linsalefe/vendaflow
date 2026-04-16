"""
VendaFlow AI — Stripe Payment Gateway
Cria Payment Links e processa webhooks do Stripe.
"""
import stripe
import hmac
import hashlib
import json
from decimal import Decimal
from app.gateways import PaymentGatewayBase, PaymentLinkRequest, PaymentLinkResult


class StripeGateway(PaymentGatewayBase):
    
    def __init__(self, secret_key: str, webhook_secret: str = None):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        stripe.api_key = secret_key
    
    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        """Cria um Stripe Checkout Session (link de pagamento)."""
        try:
            line_items = []
            for item in request.items:
                line_items.append({
                    "price_data": {
                        "currency": request.currency.lower(),
                        "product_data": {
                            "name": item["name"],
                        },
                        "unit_amount": int(Decimal(str(item["unit_price"])) * 100),
                    },
                    "quantity": item["quantity"],
                })
            
            session_params = {
                "payment_method_types": ["card", "boleto", "pix"],
                "line_items": line_items,
                "mode": "payment",
                "metadata": {
                    "order_id": str(request.order_id),
                    "order_number": request.order_number,
                    "customer_phone": request.customer_phone,
                    **(request.metadata or {}),
                },
                "payment_intent_data": {
                    "metadata": {
                        "order_id": str(request.order_id),
                        "order_number": request.order_number,
                    }
                },
            }
            
            if request.customer_email:
                session_params["customer_email"] = request.customer_email
            
            if request.success_url:
                session_params["success_url"] = request.success_url
            if request.cancel_url:
                session_params["cancel_url"] = request.cancel_url
            
            session = stripe.checkout.Session.create(**session_params)
            
            return PaymentLinkResult(
                success=True,
                gateway="stripe",
                payment_url=session.url,
                payment_link_id=session.id,
            )
        
        except stripe.error.StripeError as e:
            return PaymentLinkResult(
                success=False,
                gateway="stripe",
                error=str(e),
            )
        except Exception as e:
            return PaymentLinkResult(
                success=False,
                gateway="stripe",
                error=f"Erro inesperado: {str(e)}",
            )
    
    async def verify_payment(self, payment_id: str) -> dict:
        """Verifica status de um Checkout Session."""
        try:
            session = stripe.checkout.Session.retrieve(payment_id)
            return {
                "status": session.payment_status,
                "amount_total": session.amount_total / 100 if session.amount_total else 0,
                "customer_email": session.customer_details.email if session.customer_details else None,
                "metadata": session.metadata,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def parse_webhook(self, payload: bytes, headers: dict) -> dict:
        """Processa webhook do Stripe com verificação de assinatura."""
        sig_header = headers.get("stripe-signature", "")
        
        try:
            if self.webhook_secret:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, self.webhook_secret
                )
            else:
                event = json.loads(payload)
            
            event_type = event.get("type", "")
            data = event.get("data", {}).get("object", {})
            
            # Mapear eventos do Stripe para eventos internos
            status_map = {
                "checkout.session.completed": "approved",
                "payment_intent.succeeded": "approved",
                "payment_intent.payment_failed": "refused",
                "charge.refunded": "refunded",
                "checkout.session.expired": "expired",
            }
            
            return {
                "gateway": "stripe",
                "event_type": event_type,
                "payment_status": status_map.get(event_type, "unknown"),
                "order_id": data.get("metadata", {}).get("order_id"),
                "order_number": data.get("metadata", {}).get("order_number"),
                "amount": data.get("amount_total", 0) / 100 if "amount_total" in data else None,
                "customer_email": data.get("customer_details", {}).get("email") if "customer_details" in data else None,
                "gateway_event_id": event.get("id"),
                "raw": data,
            }
        
        except Exception as e:
            return {"gateway": "stripe", "error": str(e), "event_type": "error"}
