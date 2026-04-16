"""
VendaFlow AI — Main Application
FastAPI app principal com todas as rotas.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()

# ── Scheduler ─────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: start/stop scheduler."""
    from app.agents.abandoned_cart import process_abandoned_carts
    
    scheduler.add_job(
        process_abandoned_carts,
        "interval",
        minutes=30,
        id="abandoned_cart_check",
        replace_existing=True,
    )
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
from app.webhooks.evolution_routes import router as evolution_router
from app.webhooks.payment_webhooks import router as payment_router

app.include_router(evolution_router)
app.include_router(payment_router)

# TODO: Importar rotas conforme forem criadas
# from app.routes.auth import router as auth_router
# from app.routes.products import router as products_router
# from app.routes.orders import router as orders_router
# from app.routes.contacts import router as contacts_router
# from app.routes.dashboard import router as dashboard_router
# from app.routes.kanban import router as kanban_router
# from app.routes.ai_config import router as ai_config_router
# from app.routes.tenant import router as tenant_router

# app.include_router(auth_router)
# app.include_router(products_router)
# app.include_router(orders_router)
# app.include_router(contacts_router)
# app.include_router(dashboard_router)
# app.include_router(kanban_router)
# app.include_router(ai_config_router)
# app.include_router(tenant_router)


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
