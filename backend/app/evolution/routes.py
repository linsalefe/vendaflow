"""
Rotas do módulo Evolution API.
Gerencia instâncias WhatsApp e recebe webhooks.
Webhook aciona o Sales Agent do VendaFlow (function calling).
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import get_current_user, get_tenant_id
from sqlalchemy import select
from app.database import get_db
from app.models import Channel, Contact, Message, AIConfig
from app.evolution import client
from app.agents.sales_agent import process_sales_message
from app.evolution_client import send_text as evo_send_text, send_image as evo_send_image


router = APIRouter(prefix="/api/evolution", tags=["Evolution API"])


class CreateInstanceRequest(BaseModel):
    name: str
    purpose: str = "commercial"  # commercial, ai


# ============================================================
# INSTÂNCIAS
# ============================================================

@router.post("/instances")
async def create_instance(req: CreateInstanceRequest, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user), tenant_id: int = Depends(get_tenant_id)):
    """Cria uma instância Evolution e salva como canal."""
    # Gera nome único
    instance_name = req.name.lower().replace(" ", "_").replace("-", "_")

    try:
        result = await client.create_instance(instance_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao criar instância: {str(e)}")

    # Salvar como canal no banco
    channel = Channel(
        tenant_id=tenant_id,
        name=req.name,
        type="whatsapp",
        provider="evolution",
        instance_name=instance_name,
        is_active=True,
        is_connected=False,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)

    # Buscar QR code
    qr = await client.get_qrcode(instance_name)

    return {
        "channel_id": channel.id,
        "instance_name": instance_name,
        "purpose": req.purpose,
        "qrcode": qr,
    }


@router.get("/instances/{instance_name}/qrcode")
async def get_qrcode(instance_name: str):
    """Retorna o QR code para conectar o WhatsApp."""
    try:
        qr = await client.get_qrcode(instance_name)
        return qr
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instances/{instance_name}/status")
async def get_status(instance_name: str, db: AsyncSession = Depends(get_db)):
    """Verifica status de conexão da instância."""
    try:
        status = await client.get_instance_status(instance_name)

        # Atualizar is_connected no banco
        state = status.get("instance", {}).get("state", "close")
        is_connected = state == "open"

        result = await db.execute(
            select(Channel).where(Channel.instance_name == instance_name)
        )
        channel = result.scalar_one_or_none()
        if channel:
            channel.is_connected = is_connected
            await db.commit()

        return {"instance_name": instance_name, "state": state, "is_connected": is_connected}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/instances/{instance_name}")
async def delete_instance(instance_name: str, db: AsyncSession = Depends(get_db)):
    """Deleta a instância e remove o canal."""
    from sqlalchemy import text

    try:
        await client.delete_instance(instance_name)
    except Exception:
        pass

    result = await db.execute(
        select(Channel).where(Channel.instance_name == instance_name)
    )
    channel = result.scalar_one_or_none()
    if channel:
        ch_id = channel.id

        # 1) Buscar wa_ids e ids dos contatos deste canal
        rows = await db.execute(
            select(Contact.wa_id, Contact.id).where(Contact.channel_id == ch_id)
        )
        contact_rows = rows.fetchall()
        wa_ids = [r[0] for r in contact_rows]
        contact_ids = [r[1] for r in contact_rows]

        # 2) Deletar lead_agent_context (referencia contacts.id)
        if contact_ids:
            await db.execute(
                text("DELETE FROM lead_agent_context WHERE lead_id = ANY(:ids)"),
                {"ids": contact_ids}
            )

        if wa_ids:
            # 3) Deletar tabelas que referenciam contacts (via contact_wa_id)
            for tbl in ['activities', 'ai_calls', 'ai_conversation_summaries',
                        'contact_tags', 'financial_entries', 'messages',
                        'schedules', 'tasks']:
                await db.execute(
                    text(f"DELETE FROM {tbl} WHERE contact_wa_id = ANY(:ids)"),
                    {"ids": wa_ids}
                )

        # 4) Deletar tabelas que referenciam channels (via channel_id)
        for tbl in ['ai_configs', 'ai_conversation_summaries', 'call_logs',
                    'form_submissions', 'knowledge_documents', 'landing_pages',
                    'messages', 'schedules', 'voice_scripts']:
            await db.execute(
                text(f"DELETE FROM {tbl} WHERE channel_id = :ch_id"),
                {"ch_id": ch_id}
            )

        # 5) Deletar contatos e canal
        await db.execute(
            text("DELETE FROM contacts WHERE channel_id = :ch_id"),
            {"ch_id": ch_id}
        )
        await db.delete(channel)
        await db.commit()

    return {"status": "deleted", "instance_name": instance_name}


@router.post("/instances/{instance_name}/logout")
async def logout_instance(instance_name: str, db: AsyncSession = Depends(get_db)):
    """Desconecta o WhatsApp sem deletar a instância."""
    try:
        await client.logout_instance(instance_name)

        result = await db.execute(
            select(Channel).where(Channel.instance_name == instance_name)
        )
        channel = result.scalar_one_or_none()
        if channel:
            channel.is_connected = False
            await db.commit()

        return {"status": "logged_out", "instance_name": instance_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# WEBHOOK
# ============================================================

@router.post("/webhook/{instance_name}")
async def evolution_webhook(
    instance_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook do Evolution API — aciona Sales Agent do VendaFlow.
    URL no Evolution: POST https://seudominio.com/api/evolution/webhook/{instance_name}
    """
    import uuid
    from datetime import datetime, timezone, timedelta
    SP_TZ = timezone(timedelta(hours=-3))

    try:
        payload = await request.json()
    except Exception:
        return {"status": "invalid_json"}

    event = payload.get("event", "")

    # Só processar mensagens recebidas
    if event != "messages.upsert":
        # Tratar atualização de conexão
        if event == "connection.update":
            data = payload.get("data", {})
            state = data.get("state", "")
            result = await db.execute(
                select(Channel).where(Channel.instance_name == instance_name)
            )
            ch = result.scalar_one_or_none()
            if ch:
                ch.is_connected = (state == "open")
                await db.commit()
        return {"status": "ignored", "event": event}

    data = payload.get("data", {})
    key = data.get("key", {})

    # Ignorar mensagens enviadas por nós
    if key.get("fromMe", False):
        return {"status": "ignored", "reason": "fromMe"}

    # Ignorar protocol messages (status updates, etc)
    if data.get("messageType") == "protocolMessage":
        return {"status": "ignored", "reason": "protocol"}

    # Extrair wa_id (ignorar grupos)
    remote_jid = key.get("remoteJid", "")
    if "@g.us" in remote_jid:
        return {"status": "ignored", "reason": "group"}

    wa_id = remote_jid.replace("@s.whatsapp.net", "")
    if not wa_id:
        return {"status": "ignored", "reason": "invalid_jid"}

    push_name = data.get("pushName", "Cliente")
    message_id = key.get("id", f"evo_{uuid.uuid4().hex[:16]}")

    # Extrair texto da mensagem
    msg_type = data.get("messageType", "conversation")
    message = data.get("message", {})
    text = ""
    media_url = ""

    if msg_type == "conversation":
        text = message.get("conversation", "") or data.get("body", "")
    elif msg_type == "extendedTextMessage":
        text = message.get("extendedTextMessage", {}).get("text", "")
    elif msg_type in ("imageMessage", "videoMessage", "documentMessage"):
        caption = message.get(msg_type, {}).get("caption", "")
        text = caption or f"[{msg_type.replace('Message', '')}]"
        media_url = message.get(msg_type, {}).get("url", "")
    elif msg_type in ("audioMessage", "pttMessage"):
        # Transcrever áudio via Whisper
        try:
            import httpx
            import tempfile
            from openai import AsyncOpenAI
            audio_url = message.get(msg_type, {}).get("url", "")
            if audio_url:
                async with httpx.AsyncClient(timeout=30) as http:
                    audio_resp = await http.get(audio_url)
                    if audio_resp.status_code == 200:
                        import os
                        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                            tmp.write(audio_resp.content)
                            tmp_path = tmp.name
                        whisper = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                        with open(tmp_path, "rb") as f:
                            transcription = await whisper.audio.transcriptions.create(
                                model="whisper-1", file=f, language="pt"
                            )
                        text = transcription.text
                        os.unlink(tmp_path)
                        print(f"🎙️ Áudio transcrito: {text[:80]}")
        except Exception as e:
            print(f"⚠️ Erro ao transcrever áudio: {e}")
            text = "[áudio não transcrito]"
    elif msg_type == "listResponseMessage":
        text = message.get("listResponseMessage", {}).get("title", "")
    elif msg_type == "buttonsResponseMessage":
        text = message.get("buttonsResponseMessage", {}).get("selectedDisplayText", "")
    else:
        text = data.get("body", "") or message.get("conversation", "") or ""

    text = text.strip()
    if not text:
        return {"status": "ignored", "reason": "empty_message"}

    # ── Buscar canal ──────────────────────────────────────────────────────
    channel_result = await db.execute(
        select(Channel).where(Channel.instance_name == instance_name)
    )
    channel = channel_result.scalar_one_or_none()
    if not channel:
        print(f"⚠️ Canal não encontrado: {instance_name}")
        return {"status": "error", "reason": "channel_not_found"}

    tenant_id = channel.tenant_id

    # ── Buscar/criar contato ──────────────────────────────────────────────
    contact_result = await db.execute(
        select(Contact).where(Contact.wa_id == wa_id, Contact.tenant_id == tenant_id)
    )
    contact = contact_result.scalar_one_or_none()

    if not contact:
        contact = Contact(
            tenant_id=tenant_id,
            wa_id=wa_id,
            name=push_name,
            channel_id=channel.id,
            lead_status="novo",
            ai_active=True,
        )
        db.add(contact)
        await db.flush()

    # Atualizar dados do contato
    contact.last_inbound_at = datetime.now(SP_TZ).replace(tzinfo=None)
    if push_name and push_name != "Cliente" and (not contact.name or contact.name == "Cliente"):
        contact.name = push_name

    # ── Salvar mensagem recebida (verificar duplicata) ────────────────────
    existing = await db.execute(
        select(Message).where(Message.wa_message_id == message_id)
    )
    if existing.scalar_one_or_none():
        return {"status": "duplicate"}

    inbound_msg = Message(
        tenant_id=tenant_id,
        wa_message_id=message_id,
        contact_wa_id=wa_id,
        channel_id=channel.id,
        direction="inbound",
        message_type=msg_type,
        content=text,
        media_url=media_url or None,
        timestamp=datetime.now(SP_TZ).replace(tzinfo=None),
        status="received",
        sent_by_ai=False,
        sender_name=push_name,
    )
    db.add(inbound_msg)
    await db.commit()

    # ── Verificar se IA está ativa ────────────────────────────────────────
    if not contact.ai_active:
        return {"status": "ai_disabled_for_contact"}

    ai_config_result = await db.execute(
        select(AIConfig).where(AIConfig.channel_id == channel.id)
    )
    ai_config = ai_config_result.scalar_one_or_none()
    if not ai_config or not ai_config.is_enabled:
        return {"status": "ai_disabled_for_channel"}

    # ── Processar com Sales Agent ─────────────────────────────────────────
    print(f"🛒 [{instance_name}] {push_name} ({wa_id}): {text[:80]}")

    try:
        result = await process_sales_message(
            wa_id=wa_id,
            user_message=text,
            contact_name=push_name,
            instance_name=instance_name,
            channel_id=channel.id,
            db=db,
            tenant_id=tenant_id,
            input_message_type=msg_type,
        )
    except Exception as e:
        print(f"❌ Erro no Sales Agent: {e}")
        return {"status": "error", "detail": str(e)}

    ai_message = result.get("message", "")
    payment_url = result.get("payment_url")
    image_url_to_send = result.get("image_url")

    if not ai_message:
        return {"status": "no_response"}

    # ── Enviar imagem do produto (se houver) ──────────────────────────────
    if image_url_to_send:
        try:
            await evo_send_image(instance_name, wa_id, image_url_to_send, "")
        except Exception as e:
            print(f"⚠️ Erro ao enviar imagem: {e}")

    # ── Enviar resposta da IA ─────────────────────────────────────────────
    try:
        await evo_send_text(instance_name, wa_id, ai_message)
    except Exception as e:
        print(f"❌ Erro ao enviar resposta: {e}")

    # Salvar mensagem da IA
    ai_msg_record = Message(
        tenant_id=tenant_id,
        wa_message_id=f"ai_{uuid.uuid4().hex[:16]}",
        contact_wa_id=wa_id,
        channel_id=channel.id,
        direction="outbound",
        message_type="text",
        content=ai_message,
        timestamp=datetime.now(SP_TZ).replace(tzinfo=None),
        status="sent",
        sent_by_ai=True,
        ai_action=result.get("action"),
    )
    db.add(ai_msg_record)

    # ── Enviar link de pagamento separado (destaque) ──────────────────────
    if payment_url:
        link_message = f"💳 *Link de Pagamento*\n\nFinalize sua compra:\n{payment_url}\n\n✅ Pix, cartão ou boleto."
        try:
            await evo_send_text(instance_name, wa_id, link_message)
        except Exception as e:
            print(f"⚠️ Erro ao enviar link: {e}")

        link_record = Message(
            tenant_id=tenant_id,
            wa_message_id=f"ai_link_{uuid.uuid4().hex[:16]}",
            contact_wa_id=wa_id,
            channel_id=channel.id,
            direction="outbound",
            message_type="text",
            content=link_message,
            timestamp=datetime.now(SP_TZ).replace(tzinfo=None),
            status="sent",
            sent_by_ai=True,
            ai_action="payment_link_sent",
        )
        db.add(link_record)

    # ── Mover no pipeline automaticamente ─────────────────────────────────
    try:
        if contact.lead_status == "novo":
            contact.lead_status = "interessado"
            print(f"📊 Pipeline: {wa_id} movido novo → interessado")
    except Exception:
        pass

    await db.commit()
    print(f"🤖 [{instance_name}] → {wa_id}: {ai_message[:80]}... | tools: {result.get('tools_used', [])}")

    return {
        "status": "processed",
        "action": result.get("action"),
        "tools_used": result.get("tools_used", []),
        "payment_link_sent": bool(payment_url),
    }


# ============================================================
# ENVIAR MENSAGEM
# ============================================================

@router.post("/send")
async def send_message(
    instance_name: str,
    to: str,
    text: str,
):
    """Envia mensagem de texto pelo WhatsApp via Evolution."""
    try:
        result = await client.send_text(instance_name, to, text)
        return {"status": "sent", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
