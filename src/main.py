"""
YouTube Shorts Bot — Orquestador principal.
Pipeline: Tema → Guión → Voz → Video → Ensamblar → YouTube → Telegram

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from research import research_topic, generate_content
from voice import generate_voice_segments
from video_generator import generate_video
from pexels_fallback import download_clips
from assembler import assemble_video, generate_shorts_thumbnail
from publisher import upload_to_youtube, notify_telegram

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("main")


def load_channel(name: str) -> dict:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "channels", f"{name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config no encontrada: {path}")
    with open(path) as f:
        return json.load(f)


def find_music(project_root: str) -> str | None:
    music_dir = os.path.join(project_root, "assets", "music")
    files = glob.glob(os.path.join(music_dir, "*.mp3"))
    return random.choice(files) if files else None


def run(channel_name: str):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    work_dir = tempfile.mkdtemp(prefix=f"ytbot_{channel_name}_")

    log.info("=" * 60)
    log.info("Canal: %s", channel_name)
    log.info("=" * 60)

    # 1. Config
    channel = load_channel(channel_name)
    log.info("Canal: %s (%s)", channel["name"], channel["niche"])

    # 2. Investigar tema
    log.info("Investigando tema...")
    topic_data = research_topic(channel)
    log.info("Tema: %s", topic_data["topic"])

    # 3. Generar guión narrado
    log.info("Generando guión...")
    content = generate_content(channel, topic_data)
    log.info("Título: %s", content["title"])

    # 4. Generar voz (o segmentos silenciosos si no_voice=true)
    log.info("Generando voz...")
    segments = content.get("segments", [])
    if not segments:
        # Fallback si la IA devuelve text_slides en vez de segments
        segments = [{"voice": s.get("voice", s.get("text", "")), "text": s.get("text", "")}
                    for s in content.get("text_slides", [])]

    no_voice = channel.get("no_voice", False)
    if no_voice:
        voiced_segments = [
            {
                "text": s.get("text", s.get("voice", "")),
                "voice": s.get("voice", s.get("text", "")),
                "audio_path": None,
                "duration": 4.0,
            }
            for s in segments
        ]
        log.info("Modo sin voz: %d segmentos × 4s = %.0fs", len(voiced_segments), len(voiced_segments) * 4)
    else:
        voiced_segments = generate_voice_segments(segments, work_dir, voice="male")
        log.info("Voz generada: %d segmentos", len(voiced_segments))

    # 5. Obtener clips de video
    log.info("Obteniendo clips de video...")
    clips = generate_video(content.get("video_prompt", ""), work_dir)
    if not clips:
        search_terms = topic_data.get("search_terms", ["technology background"])
        clips = download_clips(search_terms, work_dir, num_clips=5)

    if not clips:
        raise RuntimeError("No se pudo obtener ningún clip de video")
    log.info("Clips: %d", len(clips))

    # 6. Thumbnail personalizado con el hook
    thumbnail_path = os.path.join(work_dir, "thumbnail.png")
    try:
        generate_shorts_thumbnail(
            hook=topic_data.get("hook", content["title"]),
            channel=channel,
            output_path=thumbnail_path,
            search_term=topic_data.get("search_terms", [None])[0],
        )
        log.info("Thumbnail generado")
    except Exception as e:
        log.warning("Thumbnail falló: %s", e)
        thumbnail_path = None

    # 7. Ensamblar: clips + texto + música (± voz)
    log.info("Ensamblando video...")
    output_path = os.path.join(work_dir, "final_short.mp4")
    music = find_music(project_root)

    assemble_video(
        clips=clips,
        voiced_segments=voiced_segments,
        style=channel["style"],
        output_path=output_path,
        music_path=music,
        no_voice=no_voice,
    )

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    log.info("Video final: %.1f MB", size_mb)

    # 8. Subir a YouTube
    log.info("Subiendo a YouTube...")
    video_url = upload_to_youtube(
        video_path=output_path,
        title=content["title"],
        description=content["description"],
        tags=content["tags"],
        channel_config=channel,
        thumbnail_path=thumbnail_path,
    )

    # 8. Telegram
    msg = (
        f"✅ <b>{channel['name']}</b>\n\n"
        f"📹 {content['title']}\n"
        f"🔗 {video_url}\n\n"
        f"📊 Tema: {topic_data['topic']}\n"
        f"📦 {size_mb:.1f} MB | {len(voiced_segments)} segmentos con voz"
    )
    notify_telegram(msg)

    log.info("Completado: %s", video_url)
    return video_url


def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts Bot")
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()

    try:
        url = run(args.channel)
        print(f"\nVideo: {url}")
    except Exception as e:
        log.error("Error: %s", e, exc_info=True)
        try:
            notify_telegram(f"❌ <b>Error en {args.channel}</b>\n\n{str(e)[:500]}")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
