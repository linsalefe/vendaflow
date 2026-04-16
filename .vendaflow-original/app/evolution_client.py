"""
VendaFlow AI — Evolution API Client
Envia mensagens, imagens e documentos via WhatsApp (Evolution API).
Mesma base do EduFlow.
"""
import os
import httpx

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evo.seudominio.com")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")


async def send_text(instance_name: str, to: str, text: str) -> dict:
    """Envia mensagem de texto."""
    url = f"{EVOLUTION_API_URL}/message/sendText/{instance_name}"
    payload = {
        "number": to,
        "text": text,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"apikey": EVOLUTION_API_KEY},
            )
            return resp.json()
    except Exception as e:
        print(f"❌ Erro ao enviar texto via Evolution: {e}")
        return {"error": str(e)}


async def send_image(instance_name: str, to: str, image_url: str, caption: str = "") -> dict:
    """Envia imagem com legenda."""
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{instance_name}"
    payload = {
        "number": to,
        "mediatype": "image",
        "media": image_url,
        "caption": caption,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"apikey": EVOLUTION_API_KEY},
            )
            return resp.json()
    except Exception as e:
        print(f"❌ Erro ao enviar imagem via Evolution: {e}")
        return {"error": str(e)}


async def send_document(instance_name: str, to: str, document_url: str, filename: str = "documento.pdf") -> dict:
    """Envia documento (PDF, etc)."""
    url = f"{EVOLUTION_API_URL}/message/sendMedia/{instance_name}"
    payload = {
        "number": to,
        "mediatype": "document",
        "media": document_url,
        "fileName": filename,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"apikey": EVOLUTION_API_KEY},
            )
            return resp.json()
    except Exception as e:
        print(f"❌ Erro ao enviar documento via Evolution: {e}")
        return {"error": str(e)}


async def send_buttons(instance_name: str, to: str, text: str, buttons: list) -> dict:
    """
    Envia mensagem com botões interativos.
    buttons: [{"buttonId": "1", "buttonText": {"displayText": "Ver catálogo"}}]
    """
    url = f"{EVOLUTION_API_URL}/message/sendButtons/{instance_name}"
    payload = {
        "number": to,
        "title": "",
        "description": text,
        "buttons": buttons,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"apikey": EVOLUTION_API_KEY},
            )
            return resp.json()
    except Exception as e:
        print(f"❌ Erro ao enviar botões via Evolution: {e}")
        # Fallback para texto simples
        return await send_text(instance_name, to, text)


async def send_list(instance_name: str, to: str, text: str, button_text: str, sections: list) -> dict:
    """
    Envia mensagem com lista interativa (catálogo de produtos).
    sections: [{"title": "Camisas", "rows": [{"title": "Camisa Brasil", "description": "R$89,90", "rowId": "prod_1"}]}]
    """
    url = f"{EVOLUTION_API_URL}/message/sendList/{instance_name}"
    payload = {
        "number": to,
        "title": "",
        "description": text,
        "buttonText": button_text,
        "sections": sections,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"apikey": EVOLUTION_API_KEY},
            )
            return resp.json()
    except Exception as e:
        print(f"❌ Erro ao enviar lista via Evolution: {e}")
        return await send_text(instance_name, to, text)
