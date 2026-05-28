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
from pexels_fallback import download_clips
from assembler import assemble_video, generate_shorts_thumbnail
from publisher import upload_to_youtube, notify_telegram, promote_to_telegram

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


def _extract_video_id(url: str) -> str:
    if not url:
        return ""
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    return url.rstrip("/").split("/")[-1].split("?")[0]


def log_provenance(channel_name: str, channel: dict, topic_data: dict, content: dict, video_url: str):
    """Liga video_id -> tema/hook/título generado. Desbloquea el bucle de feedback:
    luego se cruza con métricas (pull_metrics) para saber QUÉ funcionó.
    Persiste en .title_cache/provenance.jsonl (CI ya commitea ese dir)."""
    from datetime import datetime, timezone
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_dir = os.path.join(project_root, ".title_cache")
    os.makedirs(cache_dir, exist_ok=True)
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "video_id": _extract_video_id(video_url),
        "channel": channel.get("name", channel_name),
        "config": channel_name,
        "topic": topic_data.get("topic", ""),
        "hook": topic_data.get("hook", ""),
        "title": content.get("title", ""),
        "niche": channel.get("niche", ""),
    }
    with open(os.path.join(cache_dir, "provenance.jsonl"), "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log.info("Provenance: %s -> %s", rec["video_id"], rec["topic"][:50])


def run(channel_name: str, dry_run: bool = False):
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
        import random
        voice_pool = channel.get("voice_pool")
        voice_pick = random.choice(voice_pool) if voice_pool else channel.get("voice", "male")
        log.info(f"Voz seleccionada: {voice_pick}")
        voiced_segments = generate_voice_segments(segments, work_dir, voice=voice_pick)
        log.info("Voz generada: %d segmentos", len(voiced_segments))

    # 5. Obtener clips de video (solo Pexels — gratis)
    log.info("Obteniendo clips de video...")
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
        mascot=channel.get("mascot"),
    )

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    log.info("Video final: %.1f MB", size_mb)

    if dry_run:
        import shutil
        dry_dir = os.path.join(tempfile.gettempdir(), f"dryrun_{channel_name}")
        os.makedirs(dry_dir, exist_ok=True)
        final_video = os.path.join(dry_dir, "final_short.mp4")
        shutil.copy(output_path, final_video)
        final_thumb = None
        if thumbnail_path and os.path.exists(thumbnail_path):
            final_thumb = os.path.join(dry_dir, "thumbnail.png")
            shutil.copy(thumbnail_path, final_thumb)
        log.info("DRY-RUN: NO subido a YouTube ni Telegram.")
        log.info("DRY-RUN título: %s", content["title"])
        log.info("DRY-RUN vídeo: %s", final_video)
        log.info("DRY-RUN thumbnail: %s", final_thumb)
        return final_video

    # 8. Subir a YouTube
    log.info("Subiendo a YouTube...")

    # Fallback description si IA la omite o devuelve vacía
    description = content.get("description") or ""
    if not description.strip():
        hook = topic_data.get("hook") or content["title"]
        keys = topic_data.get("key_points") or []
        bullets = "\n".join(f"• {k}" for k in keys[:3])
        description = f"{hook}\n\n{bullets}".strip()
        log.warning("Description IA vacía — usando fallback con hook+key_points")

    video_url = upload_to_youtube(
        video_path=output_path,
        title=content["title"],
        description=description,
        tags=content.get("tags") or [],
        channel_config=channel,
        thumbnail_path=thumbnail_path,
    )

    # Provenance: registrar qué tema/hook generó este video_id (bucle de feedback)
    try:
        log_provenance(channel_name, channel, topic_data, content, video_url)
    except Exception as e:
        log.warning("Provenance log falló: %s", str(e)[:80])

    # 8. Telegram (admin notif + auto-promo público)
    msg = (
        f"✅ <b>{channel['name']}</b>\n\n"
        f"📹 {content['title']}\n"
        f"🔗 {video_url}\n\n"
        f"📊 Tema: {topic_data['topic']}\n"
        f"📦 {size_mb:.1f} MB | {len(voiced_segments)} segmentos con voz"
    )
    notify_telegram(msg)

    # Auto-promo: si TELEGRAM_PROMO_CHAT_ID está set, post atractivo
    promote_to_telegram(
        channel_name=channel.get("name", channel_name),
        video_title=content.get("title", ""),
        video_url=video_url,
        description=content.get("description", ""),
        tags=content.get("tags", []),
    )

    log.info("Completado: %s", video_url)
    return video_url


def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts Bot")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--no-upload", action="store_true",
                        help="Genera el vídeo pero NO sube a YouTube ni notifica (test local)")
    args = parser.parse_args()

    try:
        url = run(args.channel, dry_run=args.no_upload)
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
