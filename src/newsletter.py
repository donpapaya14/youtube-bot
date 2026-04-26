"""
Newsletter automática semanal vía Mailchimp.
Genera contenido con IA, crea campaña y envía a todos los suscriptores.
Cron: domingos 10:00 UTC.

Uso: python src/newsletter.py
"""

import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import requests
from research import _call_groq

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

API_KEY = os.getenv("MAILCHIMP_API_KEY")
LIST_ID = os.getenv("MAILCHIMP_LIST_ID")
DC = API_KEY.split("-")[-1] if API_KEY else "us5"
BASE = f"https://{DC}.api.mailchimp.com/3.0"


def generate_content() -> dict:
    """Genera newsletter semanal con IA."""
    today = datetime.now().strftime("%d/%m/%Y")

    prompt = f"""Escribe una newsletter semanal en español para suscriptores de VidaSana360.
Fecha: {today}

Los suscriptores quieren tips de salud, nutrición, pérdida de peso y bienestar.

ESTRUCTURA (escribe el HTML completo):
1. Saludo: "Hola! Esta semana traigo algo bueno..."
2. TIP DE LA SEMANA: consejo concreto de salud/nutrición con dato científico REAL (universidad + año)
3. RECETA RÁPIDA: una receta saludable en 3 pasos (ingredientes + pasos)
4. DATO CURIOSO: algo sorprendente sobre el cuerpo humano verificable
5. RETO SEMANAL: un mini reto de 7 días (ej: "camina 15 min después de cenar")
6. Despedida: "Comparte con alguien que necesite esto"

REGLAS:
- Tono cercano, como un amigo
- Datos REALES con fuente
- Máx 350 palabras
- HTML limpio con <h2>, <p>, <strong>, <ul>
- No mencionar IA

Responde JSON:
{{
  "subject": "asunto email max 50 chars que genere curiosidad",
  "html": "<h2>...</h2><p>...</p>"
}}"""

    return _call_groq(prompt, temperature=0.8)


def create_and_send_campaign(content: dict) -> str:
    """Crea campaña en Mailchimp y la envía."""
    auth = ("any", API_KEY)

    # 1. Crear campaña
    campaign = requests.post(
        f"{BASE}/campaigns",
        auth=auth,
        json={
            "type": "regular",
            "recipients": {"list_id": LIST_ID},
            "settings": {
                "subject_line": content["subject"],
                "from_name": "VidaSana360",
                "reply_to": "vladys.z96@gmail.com",
                "title": f"Newsletter {datetime.now().strftime('%d/%m')}",
            },
        },
        timeout=30,
    )
    campaign.raise_for_status()
    campaign_id = campaign.json()["id"]
    log.info("Campaña creada: %s", campaign_id)

    # 2. Poner contenido HTML
    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
    <div style="text-align: center; padding: 20px; background: #C62828; border-radius: 12px; margin-bottom: 20px;">
        <h1 style="color: white; margin: 0;">VidaSana360</h1>
        <p style="color: #EF9A9A; margin: 5px 0 0;">Tu dosis semanal de salud y bienestar</p>
    </div>
    {content['html']}
    <hr style="border: 1px solid #eee; margin: 30px 0;">
    <p style="text-align: center; color: #999; font-size: 12px;">
        Recibes esto porque te suscribiste a VidaSana360.<br>
        <a href="*|UNSUB|*">Darse de baja</a>
    </p>
    </body></html>
    """

    requests.put(
        f"{BASE}/campaigns/{campaign_id}/content",
        auth=auth,
        json={"html": html_body},
        timeout=30,
    ).raise_for_status()
    log.info("Contenido añadido")

    # 3. Enviar
    send = requests.post(f"{BASE}/campaigns/{campaign_id}/actions/send", auth=auth, timeout=30)
    if send.status_code in (200, 204):
        log.info("Newsletter enviada!")
        return f"https://{DC}.admin.mailchimp.com/campaigns/show?id={campaign_id}"
    else:
        log.error("Error enviando: %s %s", send.status_code, send.text[:300])
        raise RuntimeError(f"Error enviando: {send.status_code}")


def main():
    log.info("Generando newsletter semanal...")
    content = generate_content()
    log.info("Asunto: %s", content["subject"])

    url = create_and_send_campaign(content)
    log.info("Enviada: %s", url)

    from publisher import notify_telegram
    notify_telegram(f"📩 <b>Newsletter enviada</b>\n\n{content['subject']}")


if __name__ == "__main__":
    main()
