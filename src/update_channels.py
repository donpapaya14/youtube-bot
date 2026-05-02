"""
Actualiza nombre y descripción de los canales YouTube.
Ejecutar una sola vez: python src/update_channels.py
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("update_channels")

CHANNEL_UPDATES = {
    "YT_TOKEN_DARKFILES": {
        "name": "Chill Orbit",
        "description": (
            "🎧 Lo-fi hip hop beats for studying, relaxing and sleeping.\n\n"
            "Welcome to Chill Orbit — your cozy corner of the internet. "
            "We upload lo-fi music mixes perfect for late night study sessions, "
            "focus work, relaxation, and sleep.\n\n"
            "🎵 New mixes every week\n"
            "📚 Study beats • Chill vibes • Relaxing music\n\n"
            "Put on your headphones, relax, and orbit with us 🌙"
        ),
        "keywords": "lofi,lo-fi,study music,chill beats,relaxing music,study beats,lofi hip hop,sleep music",
    },
    "YT_TOKEN_CALMEARTH": {
        "name": "Calm Earth",
        "description": (
            "🌿 Nature sounds and ambient videos for relaxation, sleep and meditation.\n\n"
            "Calm Earth brings you immersive nature experiences — "
            "rain sounds, forest ambience, ocean waves, thunderstorms, "
            "and peaceful landscapes from around the world.\n\n"
            "🌧️ Rain & Thunder • 🌊 Ocean Waves • 🌲 Forest Sounds\n"
            "🔥 Campfire • 🐦 Birds Singing • 💧 Waterfall\n\n"
            "Perfect for sleep, meditation, study, or simply unwinding after a long day."
        ),
        "keywords": "nature sounds,ambient,relaxation,sleep sounds,meditation,white noise,ASMR nature,rain sounds",
    },
    "YT_TOKEN_CHILLORBIT": {
        "name": "Dark Files",
        "description": (
            "🔍 True crime stories, unsolved mysteries, and chilling investigations.\n\n"
            "Dark Files explores real criminal cases using publicly available "
            "court records, police reports, and news coverage. "
            "Every story is researched and fact-checked.\n\n"
            "⚖️ Real cases • 🔎 Unsolved mysteries • 📁 Cold cases\n\n"
            "New episodes every week. Subscribe and turn on notifications 🔔\n\n"
            "Disclaimer: All content is based on publicly available information. "
            "We respect the victims and their families."
        ),
        "keywords": "true crime,unsolved mysteries,cold cases,crime documentary,investigation,dark files,criminal cases",
    },
}


def update_channel(token_env: str, updates: dict):
    refresh_token = os.getenv(token_env)
    if not refresh_token:
        log.warning("Token %s no encontrado, saltando", token_env)
        return

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("YOUTUBE_CLIENT_ID"),
        client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/youtube"],
    )

    youtube = build("youtube", "v3", credentials=creds)

    # Obtener canal actual
    ch = youtube.channels().list(part="snippet,brandingSettings", mine=True).execute()
    if not ch.get("items"):
        log.error("No se encontró canal para %s", token_env)
        return

    channel = ch["items"][0]
    channel_id = channel["id"]
    current_title = channel["snippet"]["title"]

    log.info("Canal: %s (ID: %s) → actualizando a '%s'", current_title, channel_id, updates["name"])

    # Actualizar branding
    channel["brandingSettings"]["channel"]["description"] = updates["description"]
    channel["brandingSettings"]["channel"]["keywords"] = updates["keywords"]

    youtube.channels().update(
        part="brandingSettings",
        body={
            "id": channel_id,
            "brandingSettings": channel["brandingSettings"],
        },
    ).execute()

    log.info("✓ Canal %s actualizado", updates["name"])


def main():
    for token_env, updates in CHANNEL_UPDATES.items():
        try:
            update_channel(token_env, updates)
        except Exception as e:
            log.error("Error actualizando %s: %s", updates["name"], e)

    log.info("Completado")


if __name__ == "__main__":
    main()
