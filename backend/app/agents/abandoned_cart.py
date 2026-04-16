"""
VendaFlow AI — Abandoned Cart Scheduler
Envia lembretes para clientes que montaram carrinho mas não finalizaram.
"""
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import async_session
from app.models import CartItem, Contact, Channel, Tenant, AIConfig, Order, SalesConversation
from app.evolution_client import send_text

SP_TZ = timezone(timedelta(hours=-3))


async def process_abandoned_carts():
    """
    Verifica carrinhos abandonados e envia lembrete.
    Roda via APScheduler a cada 30 minutos.
    """
    async with async_session() as db:
        try:
            # Buscar tenants com abandoned_cart ativo
            tenant_result = await db.execute(select(Tenant))
            tenants = tenant_result.scalars().all()
            
            for tenant in tenants:
                features = tenant.features or {}
                if not features.get("abandoned_cart", True):
                    continue
                
                # Buscar carrinhos com itens criados há mais de X horas
                # e que NÃO tenham pedido pago
                threshold_hours = 2  # default
                
                # Buscar config da IA do primeiro canal
                channel_result = await db.execute(
                    select(Channel).where(
                        Channel.tenant_id == tenant.id,
                        Channel.is_active == True,
                    ).limit(1)
                )
                channel = channel_result.scalar_one_or_none()
                
                if channel:
                    ai_config_result = await db.execute(
                        select(AIConfig).where(AIConfig.channel_id == channel.id)
                    )
                    ai_config = ai_config_result.scalar_one_or_none()
                    if ai_config and ai_config.abandoned_cart_hours:
                        threshold_hours = ai_config.abandoned_cart_hours
                
                threshold = datetime.now(SP_TZ).replace(tzinfo=None) - timedelta(hours=threshold_hours)
                
                # Buscar contatos com carrinho abandonado
                cart_result = await db.execute(
                    select(CartItem.contact_wa_id, func.max(CartItem.created_at).label("last_added"))
                    .where(
                        CartItem.tenant_id == tenant.id,
                        CartItem.created_at < threshold,
                    )
                    .group_by(CartItem.contact_wa_id)
                )
                abandoned = cart_result.all()
                
                for row in abandoned:
                    wa_id = row[0]
                    
                    # Verificar se já tem pedido pendente/pago
                    order_result = await db.execute(
                        select(Order).where(
                            Order.contact_wa_id == wa_id,
                            Order.tenant_id == tenant.id,
                            Order.status.in_(["pending", "paid"]),
                        ).order_by(Order.created_at.desc()).limit(1)
                    )
                    if order_result.scalar_one_or_none():
                        continue  # Já tem pedido, não é abandonado
                    
                    # Verificar se já enviamos lembrete recente (nas últimas 24h)
                    conv_result = await db.execute(
                        select(SalesConversation).where(
                            SalesConversation.contact_wa_id == wa_id,
                            SalesConversation.tenant_id == tenant.id,
                            SalesConversation.stage == "abandoned_reminder_sent",
                        ).order_by(SalesConversation.updated_at.desc()).limit(1)
                    )
                    recent_reminder = conv_result.scalar_one_or_none()
                    if recent_reminder:
                        reminder_time = recent_reminder.updated_at
                        if reminder_time and (datetime.now(SP_TZ).replace(tzinfo=None) - reminder_time).total_seconds() < 86400:
                            continue  # Já enviou lembrete nas últimas 24h
                    
                    # Buscar contato e canal
                    contact_result = await db.execute(
                        select(Contact).where(
                            Contact.wa_id == wa_id,
                            Contact.tenant_id == tenant.id,
                        )
                    )
                    contact = contact_result.scalar_one_or_none()
                    if not contact or not contact.ai_active:
                        continue
                    
                    # Buscar canal do contato
                    if not contact.channel_id:
                        continue
                    
                    ch_result = await db.execute(
                        select(Channel).where(Channel.id == contact.channel_id)
                    )
                    ch = ch_result.scalar_one_or_none()
                    if not ch or not ch.instance_name:
                        continue
                    
                    # Buscar itens do carrinho para a mensagem
                    items_result = await db.execute(
                        select(CartItem).where(
                            CartItem.contact_wa_id == wa_id,
                            CartItem.tenant_id == tenant.id,
                        )
                    )
                    items = items_result.scalars().all()
                    
                    total = sum(i.unit_price * i.quantity for i in items)
                    item_count = len(items)
                    
                    # Montar mensagem customizada ou padrão
                    name = contact.name or "Oi"
                    if tenant.abandoned_cart_message:
                        message = tenant.abandoned_cart_message.replace(
                            "{nome}", name
                        ).replace(
                            "{total}", f"R${total:.2f}"
                        ).replace(
                            "{qtd}", str(item_count)
                        )
                    else:
                        message = (
                            f"Oi {name}! 😊\n\n"
                            f"Vi que você deixou {item_count} {'item' if item_count == 1 else 'itens'} "
                            f"no carrinho (total: *R${total:.2f}*).\n\n"
                            f"Quer finalizar a compra? Posso gerar o link de pagamento rapidinho! 🛒"
                        )
                    
                    # Enviar
                    try:
                        await send_text(ch.instance_name, wa_id, message)
                        print(f"🛒 Lembrete carrinho abandonado enviado para {wa_id} (tenant {tenant.id})")
                        
                        # Marcar lembrete enviado
                        if recent_reminder:
                            recent_reminder.stage = "abandoned_reminder_sent"
                            recent_reminder.updated_at = datetime.now(SP_TZ).replace(tzinfo=None)
                        else:
                            db.add(SalesConversation(
                                tenant_id=tenant.id,
                                contact_wa_id=wa_id,
                                channel_id=contact.channel_id,
                                stage="abandoned_reminder_sent",
                            ))
                    except Exception as e:
                        print(f"⚠️ Erro ao enviar lembrete para {wa_id}: {e}")
                
                await db.commit()
        
        except Exception as e:
            print(f"❌ Erro no scheduler de carrinho abandonado: {e}")
            import traceback
            traceback.print_exc()
