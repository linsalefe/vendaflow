"""
VendaFlow AI — Database Initializer
Cria todas as tabelas a partir dos models SQLAlchemy.
Uso: python init_db.py
"""
import asyncio
import sys
from app.database import engine, Base

# Importar todos os models para registrar na metadata
from app import models  # noqa: F401 (EduFlow base)
from app import sales_models  # noqa: F401 (VendaFlow)


async def create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Todas as tabelas criadas/atualizadas.")


async def drop_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("🗑️ Todas as tabelas removidas.")


async def list_tables():
    from sqlalchemy import inspect
    async with engine.connect() as conn:
        def _list(sync_conn):
            return inspect(sync_conn).get_table_names()
        tables = await conn.run_sync(_list)
    print(f"📋 Tabelas no banco ({len(tables)}):")
    for t in sorted(tables):
        print(f"  - {t}")


async def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "create"
    if cmd == "create":
        await create_all()
        await list_tables()
    elif cmd == "drop":
        confirm = input("⚠️ CONFIRMA drop de todas as tabelas? (digite 'sim'): ")
        if confirm.strip().lower() == "sim":
            await drop_all()
        else:
            print("Cancelado.")
    elif cmd == "reset":
        confirm = input("⚠️ CONFIRMA reset (drop + create)? (digite 'sim'): ")
        if confirm.strip().lower() == "sim":
            await drop_all()
            await create_all()
            await list_tables()
        else:
            print("Cancelado.")
    elif cmd == "list":
        await list_tables()
    else:
        print(f"Comando inválido: {cmd}")
        print("Uso: python init_db.py [create|drop|reset|list]")


if __name__ == "__main__":
    asyncio.run(main())
