"""
VendaFlow AI — Payment Gateway Abstraction
Interface unificada para Stripe, Hotmart, Kiwify.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


@dataclass
class PaymentLinkResult:
    """Resultado da criação de um link de pagamento."""
    success: bool
    gateway: str
    payment_url: str = ""
    payment_link_id: str = ""
    error: str = ""
    expires_at: Optional[str] = None


@dataclass
class PaymentLinkRequest:
    """Dados para criar um link de pagamento."""
    order_id: int
    order_number: str
    customer_name: str
    customer_email: Optional[str]
    customer_phone: str
    items: list  # [{"name": str, "quantity": int, "unit_price": Decimal}]
    total: Decimal
    currency: str = "BRL"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None
    metadata: dict = None


class PaymentGatewayBase(ABC):
    """Interface base para gateways de pagamento."""
    
    @abstractmethod
    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLinkResult:
        """Cria um link de pagamento."""
        pass
    
    @abstractmethod
    async def verify_payment(self, payment_id: str) -> dict:
        """Verifica status de um pagamento."""
        pass
    
    @abstractmethod
    def parse_webhook(self, payload: dict, headers: dict) -> dict:
        """Processa webhook do gateway."""
        pass
