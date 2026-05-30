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


def _amazon_domain(channel_config: dict) -> str:
    """amazon.es para canales ES, amazon.com para el resto."""
    lang = (channel_config.get("language") or "en").lower()
    return "amazon.es" if lang.startswith("es") else "amazon.com"


def _affiliate_disclosure(channel_config: dict) -> str:
    """Disclosure obligatorio de Amazon Associates."""
    lang = (channel_config.get("language") or "en").lower()
    if lang.startswith("es"):
        return "Como afiliado de Amazon, gano por compras que califican."
    return "As an Amazon Associate I earn from qualifying purchases."


def build_affiliate_block(channel_config: dict, tags: list[str] | None = None) -> str:
    """Bloque afiliado Amazon para la PRIMERA línea de la descripción.
    Central: cualquier canal con amazon_tag + amazon_search lo emite,
    así no depende del CTA canal-por-canal y el link queda arriba (YouTube
    corta la descripción tras ~3 líneas)."""
    tag = channel_config.get("amazon_tag")
    keyword = channel_config.get("amazon_search")
    if not tag or not keyword:
        return ""
    domain = _amazon_domain(channel_config)
    url = f"https://www.{domain}/s?k={keyword}&tag={tag}"
    label = channel_config.get(
        "affiliate_label",
        "🛒 Recomendados" if domain == "amazon.es" else "🛒 Recommended",
    )
    return f"{label} ↓\n{url}\n{_affiliate_disclosure(channel_config)}"


def _compose_description(
    channel_config: dict,
    description: str,
    tags: list[str] | None = None,
    cta_key: str = "cta",
) -> str:
    """Antepone el bloque afiliado (línea 1) y añade el CTA del canal al final."""
    parts = []
    block = build_affiliate_block(channel_config, tags)
    if block:
        parts.append(block)
    if description:
        parts.append(description)
    cta = (channel_config.get(cta_key) or "").strip()
    if cta:
        parts.append(cta)
    return "\n\n".join(parts)


def build_pinned_comment(channel_config: dict, tags: list[str] | None = None) -> str:
    """Comentario con link afiliado garantizado (cae al pinned_comment del canal)."""
    base = (channel_config.get("pinned_comment") or "").strip()
    block = build_affiliate_block(channel_config, tags)
    if block and "amazon" not in base.lower():
        return f"{base}\n\n{block}".strip() if base else block
    return base


def _insert_pinned_comment(
    youtube, video_id: str, channel_config: dict, tags: list[str] | None = None
) -> None:
    """Publica comentario con afiliado. OJO: commentThreads().insert NO fija el
    comentario (la API de YouTube no expone 'pin' de forma fiable); el link
    afiliado garantizado va en la línea 1 de la descripción."""
    text = build_pinned_comment(channel_config, tags)
    if not text:
        return
    try:
        youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {"snippet": {"textOriginal": text}},
                }
            },
        ).execute()
        log.info("Comentario publicado")
    except Exception as e:
        log.warning("Error publicando comentario: %s", e)


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    channel_config: dict,
    thumbnail_path: str | None = None,
) -> str:
    """Sube video a YouTube. Devuelve URL del video."""
    token_env = channel_config.get("refresh_token_env", "YOUTUBE_REFRESH_TOKEN")
    refresh_token = os.getenv(token_env)

    # Multi-project: cada canal usa el client_id de su cloud_project
    project = channel_config.get("cloud_project", "default")
    if project == "default":
        cid_env, csec_env = "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"
    else:
        cid_env = f"YOUTUBE_{project.upper()}_CLIENT_ID"
        csec_env = f"YOUTUBE_{project.upper()}_CLIENT_SECRET"
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv(cid_env),
        client_secret=os.getenv(csec_env),
        scopes=["https://www.googleapis.com/auth/youtube"],
    )

    youtube = build("youtube", "v3", credentials=creds)

    # Descripción: bloque afiliado en línea 1 + cuerpo + CTA del canal al final
    description = _compose_description(channel_config, description, tags, cta_key="cta")

    language = channel_config.get("language", "en")
    category_id = channel_config.get("category_id", "22")

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": list(set(tags))[:30],
            "categoryId": category_id,
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
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

    # Subir thumbnail si existe
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/png"),
            ).execute()
            log.info("Thumbnail subido")
        except Exception as e:
            log.warning("Error subiendo thumbnail: %s", e)

    video_url = f"https://youtube.com/shorts/{video_id}"
    log.info("Video publicado: %s", video_url)

    # Comentario con link afiliado (no se fija por límite de la API)
    _insert_pinned_comment(youtube, video_id, channel_config, tags)

    return video_url


def upload_to_youtube_longform(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    channel_config: dict,
    thumbnail_path: str | None = None,
) -> str:
    """Sube video long-form a YouTube. Devuelve URL del video."""
    token_env = channel_config.get("refresh_token_env", "YOUTUBE_REFRESH_TOKEN")
    refresh_token = os.getenv(token_env)

    # Multi-project: cada canal usa el client_id de su cloud_project
    project = channel_config.get("cloud_project", "default")
    if project == "default":
        cid_env, csec_env = "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"
    else:
        cid_env = f"YOUTUBE_{project.upper()}_CLIENT_ID"
        csec_env = f"YOUTUBE_{project.upper()}_CLIENT_SECRET"
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv(cid_env),
        client_secret=os.getenv(csec_env),
        scopes=["https://www.googleapis.com/auth/youtube"],
    )

    youtube = build("youtube", "v3", credentials=creds)

    category_id = channel_config.get("category_id", "22")
    language = channel_config.get("language", "en")

    # Anteponer bloque afiliado en línea 1 (la descripción ya trae el CTA del canal)
    block = build_affiliate_block(channel_config, tags)
    if block:
        description = f"{block}\n\n{description}"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": list(set(tags))[:30],
            "categoryId": category_id,
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=25 * 1024 * 1024,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    log.info("Subiendo video long-form a YouTube...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            log.info("Subido: %d%%", int(status.progress() * 100))

    video_id = response["id"]

    # Subir thumbnail si existe
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path, mimetype="image/png"),
            ).execute()
            log.info("Thumbnail subido")
        except Exception as e:
            log.warning("Error subiendo thumbnail: %s", e)

    video_url = f"https://youtube.com/watch?v={video_id}"
    log.info("Video publicado: %s", video_url)

    # Comentario con link afiliado (longform antes no publicaba ninguno)
    _insert_pinned_comment(youtube, video_id, channel_config, tags)

    return video_url


def notify_telegram(message: str) -> bool:
    """Envía notificación por Telegram (admin chat)."""
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


def promote_to_telegram(channel_name: str, video_title: str, video_url: str,
                        description: str = "", tags: list = None) -> bool:
    """Auto-promo a canal Telegram público (separado del admin notif).
    Genera post atractivo con hooks + hashtags + CTA.
    Set TELEGRAM_PROMO_CHAT_ID al @canal_publico o ID numérico."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    promo_chat = os.getenv("TELEGRAM_PROMO_CHAT_ID")

    if not token or not promo_chat:
        return False

    # Formato post promo atractivo
    hashtags = " ".join(f"#{t.replace(' ','')}" for t in (tags or [])[:5])
    post = (
        f"🔥 <b>{video_title}</b>\n\n"
        f"{description[:200]}{'...' if len(description) > 200 else ''}\n\n"
        f"▶️ Ver ahora: {video_url}\n\n"
        f"📺 Canal: {channel_name}\n"
        f"{hashtags}"
    )

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={
            "chat_id": promo_chat,
            "text": post,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=30)
        resp.raise_for_status()
        log.info("Promo Telegram enviada al canal público")
        return True
    except Exception as e:
        log.error("Error promo Telegram: %s", e)
        return False
