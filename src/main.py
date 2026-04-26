"""
YouTube Shorts Bot — Orquestador principal.
Genera y publica un Short para un canal específico.

Uso: python src/main.py --channel finanzas_clara
"""

import argparse
import glob
import json
import logging
import os
import random
import sys
import tempfile

# Asegurar imports desde src/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from research import research_topic, generate_content
from video_generator import generate_video
from pexels_fallback import download_clips
from assembler import assemble_video
from publisher import upload_to_youtube, notify_telegram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


def load_channel(name: str) -> dict:
    """Carga configuración del canal desde channels/*.json."""
    # Buscar en directorio channels/ relativo al proyecto
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "channels", f"{name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config no encontrada: {path}")
    with open(path) as f:
        return json.load(f)


def find_music(project_root: str) -> str | None:
    """Busca un archivo de música aleatorio en assets/music/."""
    music_dir = os.path.join(project_root, "assets", "music")
    files = glob.glob(os.path.join(music_dir, "*.mp3"))
    if files:
        return random.choice(files)
    return None


def run(channel_name: str):
    """Pipeline completo para un canal."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work_dir = tempfile.mkdtemp(prefix=f"ytbot_{channel_name}_")

    log.info("=" * 60)
    log.info("Canal: %s", channel_name)
    log.info("Directorio temporal: %s", work_dir)
    log.info("=" * 60)

    # 1. Cargar config del canal
    channel = load_channel(channel_name)
    log.info("Canal cargado: %s (%s)", channel["name"], channel["niche"])

    # 2. Investigar tema trending
    log.info("Investigando tendencias...")
    topic_data = research_topic(channel)
    log.info("Tema: %s", topic_data["topic"])

    # 3. Generar contenido (título, descripción, tags, slides, prompt video)
    log.info("Generando contenido...")
    content = generate_content(channel, topic_data)
    log.info("Título: %s", content["title"])

    # 4. Intentar generar video con Veo 2
    log.info("Intentando Veo 2...")
    clips = generate_video(content["video_prompt"], work_dir)

    # 5. Fallback a Pexels si Veo 2 falla
    if not clips:
        log.info("Usando Pexels como fallback...")
        search_terms = topic_data.get("search_terms", ["abstract background"])
        clips = download_clips(search_terms, work_dir, num_clips=4)

    if not clips:
        raise RuntimeError("No se pudo obtener ningún clip de video")

    log.info("Clips obtenidos: %d", len(clips))

    # 6. Ensamblar video con FFmpeg
    log.info("Ensamblando video...")
    output_path = os.path.join(work_dir, "final_short.mp4")
    music = find_music(project_root)
    if music:
        log.info("Música: %s", os.path.basename(music))

    assemble_video(
        clips=clips,
        text_slides=content["text_slides"],
        style=channel["style"],
        output_path=output_path,
        music_path=music,
    )

    # Verificar que el video existe y tiene tamaño razonable
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    log.info("Video final: %.1f MB", size_mb)

    # 7. Subir a YouTube
    log.info("Subiendo a YouTube...")
    video_url = upload_to_youtube(
        video_path=output_path,
        title=content["title"],
        description=content["description"],
        tags=content["tags"],
        channel_config=channel,
    )

    # 8. Notificar por Telegram
    msg = (
        f"✅ <b>{channel['name']}</b>\n\n"
        f"📹 {content['title']}\n"
        f"🔗 {video_url}\n\n"
        f"📊 Tema: {topic_data['topic']}\n"
        f"📦 Tamaño: {size_mb:.1f} MB"
    )
    notify_telegram(msg)

    log.info("¡Completado! %s", video_url)
    return video_url


def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts Bot")
    parser.add_argument(
        "--channel",
        required=True,
        help="Nombre del canal (ej: finanzas_clara)",
    )
    args = parser.parse_args()

    try:
        url = run(args.channel)
        print(f"\nVideo publicado: {url}")
    except Exception as e:
        log.error("Error fatal: %s", e, exc_info=True)
        # Notificar error por Telegram
        try:
            notify_telegram(
                f"❌ <b>Error en {args.channel}</b>\n\n{str(e)[:500]}"
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
