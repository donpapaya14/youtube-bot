"""
Sube videos generados con Gemini Pro/Veo 2 a YouTube.
Busca videos en ~/Descargas/videos-yt/ o carpeta especificada.
Cada video se sube con metadata generada por IA.

Uso:
  python src/upload_gemini_videos.py                          # Busca en ~/Descargas/videos-yt/
  python src/upload_gemini_videos.py --folder /ruta/videos    # Carpeta custom
  python src/upload_gemini_videos.py --channel ia_explica     # Canal específico
"""

import argparse
import glob
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from research import _call_groq
from publisher import upload_to_youtube, notify_telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DEFAULT_FOLDER = os.path.expanduser("~/Descargas/videos-yt")
DEFAULT_CHANNEL = "ia_explica"


def generate_metadata(video_filename: str) -> dict:
    """Genera título, descripción y tags con IA basándose en el nombre del archivo."""
    prompt = f"""Genera metadata para un YouTube Short en español sobre IA/tecnología.
El archivo de video se llama: {video_filename}

Genera contenido atractivo y SEO-optimizado.
Responde SOLO con JSON válido:
{{
  "title": "título SEO máx 70 chars con emoji",
  "description": "descripción 3-4 líneas con keywords y CTA. Incluir: 📩 Suscríbete a la newsletter | 👍 Like y suscríbete | 🔔 Activa la campanita",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"]
}}"""
    return _call_groq(prompt, temperature=0.8)


def upload_batch(folder: str, channel_name: str):
    """Sube todos los videos MP4 de una carpeta."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "channels", f"{channel_name}.json")

    if not os.path.exists(config_path):
        log.error("Canal no encontrado: %s", config_path)
        return

    with open(config_path) as f:
        channel_config = json.load(f)

    videos = sorted(glob.glob(os.path.join(folder, "*.mp4")))
    if not videos:
        log.info("No hay videos en %s", folder)
        return

    log.info("Encontrados %d videos en %s", len(videos), folder)
    uploaded = []

    for video_path in videos:
        filename = os.path.basename(video_path)
        log.info("Procesando: %s", filename)

        try:
            # Generar metadata con IA
            meta = generate_metadata(filename)
            log.info("Título: %s", meta["title"])

            # Subir
            url = upload_to_youtube(
                video_path=video_path,
                title=meta["title"],
                description=meta["description"],
                tags=meta["tags"],
                channel_config=channel_config,
            )

            uploaded.append({"file": filename, "url": url, "title": meta["title"]})

            # Mover video a subcarpeta "subidos"
            done_dir = os.path.join(folder, "subidos")
            os.makedirs(done_dir, exist_ok=True)
            os.rename(video_path, os.path.join(done_dir, filename))

            log.info("Subido y movido: %s → %s", filename, url)

        except Exception as e:
            log.error("Error con %s: %s", filename, e)

    # Notificar por Telegram
    if uploaded:
        lines = [f"📤 <b>{len(uploaded)} videos subidos a {channel_config['name']}</b>\n"]
        for v in uploaded:
            lines.append(f"• {v['title']}\n  {v['url']}")
        notify_telegram("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Subir videos de Gemini a YouTube")
    parser.add_argument("--folder", default=DEFAULT_FOLDER, help="Carpeta con videos MP4")
    parser.add_argument("--channel", default=DEFAULT_CHANNEL, help="Canal destino")
    args = parser.parse_args()

    os.makedirs(args.folder, exist_ok=True)
    upload_batch(args.folder, args.channel)


if __name__ == "__main__":
    main()
