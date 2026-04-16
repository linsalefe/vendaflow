"""
VendaFlow AI — Sales Agent Tools (Function Calling)
Tools que a IA de vendas pode chamar para operar o CRM.
"""

SALES_AGENT_TOOLS = [
    # ─── CATÁLOGO ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Busca produtos no catálogo por nome, categoria ou tags. "
                "Use quando o cliente perguntar sobre produtos disponíveis, "
                "preços, ou demonstrar interesse em algum item."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca (ex: 'camisa brasil', 'kit blusas', 'seleção argentina')"
                    },
                    "category": {
                        "type": "string",
                        "description": "Filtrar por categoria (ex: 'camisas', 'kits', 'digitais')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Máximo de resultados (default: 5)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": (
                "Retorna detalhes completos de um produto: descrição, preços "
                "(varejo e atacado), variantes (tamanhos/cores), estoque, imagens. "
                "Use quando o cliente quiser saber mais sobre um produto específico."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "ID do produto"
                    }
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": (
                "Verifica disponibilidade de estoque de um produto/variante. "
                "Use antes de adicionar ao carrinho para garantir disponibilidade."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "ID do produto"
                    },
                    "variant_id": {
                        "type": "integer",
                        "description": "ID da variante (se aplicável)"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Quantidade desejada"
                    }
                },
                "required": ["product_id", "quantity"]
            }
        }
    },
    
    # ─── CARRINHO ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": (
                "Adiciona um produto ao carrinho do cliente. "
                "Use quando o cliente confirmar que quer comprar um item. "
                "Calcula automaticamente preço atacado se quantidade atingir o mínimo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "integer",
                        "description": "ID do produto"
                    },
                    "variant_id": {
                        "type": "integer",
                        "description": "ID da variante (tamanho/cor)"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Quantidade"
                    }
                },
                "required": ["product_id", "quantity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "view_cart",
            "description": (
                "Mostra o carrinho atual do cliente com todos os itens, "
                "quantidades, preços e total. Use para confirmar antes de gerar link."
            ),
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_cart",
            "description": "Remove um item do carrinho do cliente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cart_item_id": {
                        "type": "integer",
                        "description": "ID do item no carrinho"
                    }
                },
                "required": ["cart_item_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_cart_quantity",
            "description": "Atualiza a quantidade de um item no carrinho.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cart_item_id": {
                        "type": "integer",
                        "description": "ID do item no carrinho"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Nova quantidade"
                    }
                },
                "required": ["cart_item_id", "quantity"]
            }
        }
    },
    
    # ─── CUPOM ─────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "apply_coupon",
            "description": (
                "Aplica um cupom de desconto ao pedido do cliente. "
                "Valida se o cupom existe, está ativo e não expirou."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "coupon_code": {
                        "type": "string",
                        "description": "Código do cupom (ex: 'PROMO10')"
                    }
                },
                "required": ["coupon_code"]
            }
        }
    },
    
    # ─── PEDIDO + PAGAMENTO ────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_order_and_payment_link",
            "description": (
                "AÇÃO FINAL DE VENDA: Cria o pedido a partir do carrinho e gera "
                "o link de pagamento (Stripe, Hotmart ou Kiwify). "
                "Retorna a URL para o cliente pagar. "
                "Use quando o cliente confirmar que quer finalizar a compra."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_email": {
                        "type": "string",
                        "description": "E-mail do cliente (se coletado)"
                    },
                    "gateway_preference": {
                        "type": "string",
                        "enum": ["stripe", "hotmart", "kiwify"],
                        "description": "Gateway preferido (pix, cartão, boleto). Default: configuração do tenant."
                    },
                    "coupon_code": {
                        "type": "string",
                        "description": "Cupom aplicado (se houver)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_order_status",
            "description": (
                "Verifica o status de um pedido existente. "
                "Use quando o cliente perguntar sobre o status da compra."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_number": {
                        "type": "string",
                        "description": "Número do pedido"
                    }
                },
                "required": ["order_number"]
            }
        }
    },
    
    # ─── CRM ───────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "collect_customer_data",
            "description": (
                "Salva dados coletados do cliente durante a conversa: "
                "nome, email, CPF, endereço, preferências. "
                "Use conforme o cliente for fornecendo informações."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Nome completo"},
                    "email": {"type": "string", "description": "E-mail"},
                    "cpf": {"type": "string", "description": "CPF"},
                    "cep": {"type": "string", "description": "CEP"},
                    "is_wholesale": {
                        "type": "boolean",
                        "description": "Se é cliente atacado"
                    },
                    "preferences": {
                        "type": "object",
                        "description": "Preferências livres (tamanho, cor, etc.)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_pipeline",
            "description": (
                "Move o lead no pipeline de vendas do CRM. "
                "A IA chama automaticamente conforme a conversa avança."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_stage": {
                        "type": "string",
                        "enum": [
                            "novo", "interessado", "carrinho",
                            "link_enviado", "pago", "enviado",
                            "entregue", "perdido"
                        ],
                        "description": "Novo estágio do pipeline"
                    }
                },
                "required": ["target_stage"]
            }
        }
    },
    
    # ─── UPSELL ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_upsell_suggestions",
            "description": (
                "Busca sugestões de upsell/cross-sell baseado nos itens "
                "do carrinho atual. Use após o cliente adicionar um produto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "current_product_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "IDs dos produtos no carrinho"
                    }
                },
                "required": ["current_product_ids"]
            }
        }
    },
]
