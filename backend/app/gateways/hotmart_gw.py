"""
VendaFlow AI — Hotmart Payment Gateway
Gera links de checkout do Hotmart e processa webhooks (Hottok).
"""
import httpx
import hmac
import hashlib
from decimal import Decimal
from urllib.parse import urlencode
from app.gateways import PaymentGatewayBase, PaymentLinkRequest, PaymentLinkResult

HOTMART_API_BASE = "https://developers.hotmart.com/payments/api/v1"


class HotmartGateway(PaymentGatewayBase):
    
    def __init__(self, token: str, hottok: str = None):
        self.token = token
        self.hottok = hottok
    
    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        """
        Gera link de checkout do Hotmart.
        
        Para Hotmart, usamos o checkout nativo. O produto já existe no Hotmart,
        então montamos a URL com parâmetros do comprador.
        """
        try:
            # Para Hotmart, cada produto tem seu próprio checkout
            # O external_product_id deve ser o product code do Hotmart
            # e external_offer_id o offer code
            metadata = request.metadata or {}
            product_code = metadata.get("external_product_id", "")
            offer_code = metadata.get("external_offer_id", "")
            
            if not product_code:
                return PaymentLinkResult(
                    success=False,
                    gateway="hotmart",
                    error="Product code do Hotmart não configurado no produto.",
                )
            
            # Montar URL de checkout do Hotmart
            base_url = f"https://pay.hotmart.com/{product_code}"
            
            params = {
                "off": offer_code,
                "checkoutMode": "10",  # checkout transparente
                "bid": request.order_number,
                "name": request.customer_name,
                "phonenumber": request.customer_phone,
            }
            
            if request.customer_email:
                params["email"] = request.customer_email
            
            # Limpar params vazios
            params = {k: v for k, v in params.items() if v}
            
            checkout_url = f"{base_url}?{urlencode(params)}"
            
            return PaymentLinkResult(
                success=True,
                gateway="hotmart",
                payment_url=checkout_url,
                payment_link_id=f"hotmart_{request.order_number}",
            )
        
        except Exception as e:
            return PaymentLinkResult(
                success=False,
                gateway="hotmart",
                error=f"Erro ao gerar link Hotmart: {str(e)}",
            )
    
    async def verify_payment(self, payment_id: str) -> dict:
        """Verifica status de uma compra no Hotmart via API."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{HOTMART_API_BASE}/sales/history",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    },
                    params={"transaction": payment_id},
                    timeout=15,
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    if items:
                        purchase = items[0]
                        return {
                            "status": purchase.get("purchase", {}).get("status", "unknown"),
                            "amount_total": purchase.get("purchase", {}).get("price", {}).get("value", 0),
                            "buyer_email": purchase.get("buyer", {}).get("email"),
                        }
                
                return {"status": "not_found"}
        
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def parse_webhook(self, payload: dict, headers: dict) -> dict:
        """
        Processa webhook do Hotmart (Hottok).
        
        Hotmart envia POST com JSON no body.
        Eventos principais: PURCHASE_COMPLETE, PURCHASE_CANCELED, 
        PURCHASE_REFUNDED, PURCHASE_EXPIRED, etc.
        """
        try:
            # Verificar Hottok
            received_hottok = payload.get("hottok", "")
            if self.hottok and received_hottok != self.hottok:
                return {"gateway": "hotmart", "error": "Hottok inválido", "event_type": "error"}
            
            event_type = payload.get("event", "")
            data = payload.get("data", {})
            purchase = data.get("purchase", {})
            buyer = data.get("buyer", {})
            product = data.get("product", {})
            
            # Mapear eventos do Hotmart
            status_map = {
                "PURCHASE_COMPLETE": "approved",
                "PURCHASE_APPROVED": "approved",
                "PURCHASE_CANCELED": "refused",
                "PURCHASE_REFUNDED": "refunded",
                "PURCHASE_EXPIRED": "expired",
                "PURCHASE_DELAYED": "pending",
                "PURCHASE_PROTEST": "disputed",
                "PURCHASE_CHARGEBACK": "refunded",
            }
            
            return {
                "gateway": "hotmart",
                "event_type": event_type,
                "payment_status": status_map.get(event_type, "unknown"),
                "order_number": purchase.get("tracking", {}).get("source_sck") or purchase.get("transaction"),
                "amount": purchase.get("price", {}).get("value"),
                "customer_email": buyer.get("email"),
                "customer_name": buyer.get("name"),
                "customer_phone": buyer.get("phone") or buyer.get("cellphone"),
                "product_name": product.get("name"),
                "gateway_event_id": purchase.get("transaction"),
                "raw": data,
            }
        
        except Exception as e:
            return {"gateway": "hotmart", "error": str(e), "event_type": "error"}
