"""
VendaFlow AI — Gateway Factory
Seleciona e instancia o gateway correto por tenant/produto.
"""
from app.gateways import PaymentGatewayBase
from app.gateways.stripe_gw import StripeGateway
from app.gateways.hotmart_gw import HotmartGateway
from app.gateways.kiwify_gw import KiwifyGateway
from app.models import Tenant, Product


def get_gateway(tenant: Tenant, product: Product = None) -> PaymentGatewayBase:
    """
    Retorna a instância do gateway correto.
    
    Prioridade:
    1. Gateway override do produto (se configurado)
    2. Gateway default do tenant
    """
    gateway_name = tenant.default_gateway or "stripe"
    
    # Override do produto
    if product and product.gateway_override:
        gateway_name = product.gateway_override
    
    if gateway_name == "stripe":
        return StripeGateway(
            secret_key=tenant.stripe_secret_key or "",
            webhook_secret=tenant.stripe_webhook_secret,
        )
    
    elif gateway_name == "hotmart":
        return HotmartGateway(
            token=tenant.hotmart_token or "",
            hottok=tenant.hotmart_hottok,
        )
    
    elif gateway_name == "kiwify":
        return KiwifyGateway(
            api_key=tenant.kiwify_api_key or "",
            webhook_secret=tenant.kiwify_webhook_secret,
        )
    
    else:
        raise ValueError(f"Gateway não suportado: {gateway_name}")


def get_all_gateways(tenant: Tenant) -> dict:
    """Retorna todos os gateways configurados do tenant."""
    gateways = {}
    
    if tenant.stripe_secret_key:
        gateways["stripe"] = StripeGateway(
            secret_key=tenant.stripe_secret_key,
            webhook_secret=tenant.stripe_webhook_secret,
        )
    
    if tenant.hotmart_token:
        gateways["hotmart"] = HotmartGateway(
            token=tenant.hotmart_token,
            hottok=tenant.hotmart_hottok,
        )
    
    if tenant.kiwify_api_key:
        gateways["kiwify"] = KiwifyGateway(
            api_key=tenant.kiwify_api_key,
            webhook_secret=tenant.kiwify_webhook_secret,
        )
    
    return gateways
