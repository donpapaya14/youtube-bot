"""
Publicación en YouTube + notificación por Telegram.
"""

import logging
import os
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    channel_config: dict,
) -> str:
    """Sube video a YouTube. Devuelve URL del video."""
    token_env = channel_config.get("refresh_token_env", "YOUTUBE_REFRESH_TOKEN")
    refresh_token = os.getenv(token_env)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("YOUTUBE_CLIENT_ID"),
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    youtube = build("youtube", "v3", credentials=creds)

    # Añadir CTA (web, Amazon, newsletter) al final de la descripción
    cta = channel_config.get("cta", "")
    if cta:
        description = f"{description}\n\n{cta}"

    # Añadir link Amazon basado en tags del video
    amazon_tag = channel_config.get("amazon_tag", "vladys-21")
    if tags:
        search_kw = "+".join(tags[:3]).replace(" ", "+")
        amazon_link = f"https://www.amazon.es/s?k={search_kw}&tag={amazon_tag}"
        description = description.replace(
            channel_config.get("amazon_search", ""),
            "+".join(tags[:2]).replace(" ", "+")
        ) if channel_config.get("amazon_search") else description

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "es",
            "defaultAudioLanguage": "es",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "shorts": {"shortsEligibility": "eligible"},
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    log.info("Subiendo video a YouTube...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log.info("Subido: %d%%", int(status.progress() * 100))

    video_id = response["id"]
    video_url = f"https://youtube.com/shorts/{video_id}"
    log.info("Video publicado: %s", video_url)
    return video_url


def notify_telegram(message: str) -> bool:
    """Envía notificación por Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        log.warning("Telegram no configurado, saltando notificación")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        resp = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=30,
        )
        resp.raise_for_status()
        log.info("Notificación Telegram enviada")
        return True
    except Exception as e:
        log.error("Error enviando Telegram: %s", e)
        return False
