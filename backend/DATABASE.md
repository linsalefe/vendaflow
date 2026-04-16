# Banco de Dados — VendaFlow AI

## Gerar schema inicial

Com a venv ativa e `.env` configurado:

```bash
python init_db.py create
```

Isso cria todas as tabelas definidas nos models SQLAlchemy (base EduFlow + VendaFlow).

## Resetar (drop + create)

⚠️ APAGA TODOS OS DADOS:

```bash
python init_db.py reset
```

## Listar tabelas

```bash
python init_db.py list
```
