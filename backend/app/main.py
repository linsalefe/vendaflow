"""
VendaFlow AI — Main Application
FastAPI app principal com base EduFlow adaptada para vendas.
"""
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import timezone, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

SP_TZ = timezone(timedelta(hours=-3))

# ── Scheduler ─────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: start/stop scheduler."""
    # Abandoned cart check a cada 30 minutos
    try:
        from app.agents.abandoned_cart import process_abandoned_carts
        scheduler.add_job(
            process_abandoned_carts,
            "interval",
            minutes=30,
            id="abandoned_cart_check",
            replace_existing=True,
        )
    except Exception as e:
        print(f"⚠️ Não foi possível registrar abandoned_cart job: {e}")

    scheduler.start()
    print("✅ VendaFlow AI iniciado | Scheduler ativo")

    yield

    scheduler.shutdown()
    print("🛑 VendaFlow AI encerrado")


# ── App ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="VendaFlow AI",
    description="CRM de vendas com IA que vai até o checkout",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rotas ─────────────────────────────────────────────────────────────────
# Core EduFlow (base mantida)
from app.routes import router
from app.auth_routes import router as auth_router
from app.tenant_routes import router as tenant_router, tenant_router as tenant_agent_router
from app.kanban_routes import router as kanban_router
from app.ai_routes import router as ai_router
from app.webhook_routes import router as webhook_router, public_router as webhook_public_router
from app.oauth_routes import router as oauth_router
from app.notification_routes import router as notification_router
from app.stripe_routes import router as stripe_router
from app.evolution.routes import router as evolution_router

app.include_router(router)
app.include_router(auth_router)
app.include_router(tenant_router)
app.include_router(tenant_agent_router)
app.include_router(kanban_router)
app.include_router(ai_router)
app.include_router(webhook_router)
app.include_router(webhook_public_router)
app.include_router(oauth_router)
app.include_router(notification_router)
app.include_router(stripe_router)
app.include_router(evolution_router)

# VendaFlow: rotas de vendas
from app.product_routes import router as product_router
from app.order_routes import router as order_router
from app.coupon_routes import router as coupon_router
from app.gateway_routes import router as gateway_router
app.include_router(product_router)
app.include_router(order_router)
app.include_router(coupon_router)
app.include_router(gateway_router)

# Webhooks de pagamento do VendaFlow
from app.webhooks.payment_webhooks import router as payment_router
app.include_router(payment_router)


@app.get("/")
async def root():
    return {
        "app": "VendaFlow AI",
        "version": "1.0.0",
        "status": "running",
        "description": "CRM de vendas com IA - do atendimento ao checkout",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
