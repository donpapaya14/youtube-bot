"""
Sube videos de Gemini Pro a YouTube como Shorts.
- Convierte a vertical 9:16 automáticamente
- Genera títulos SEO relevantes al canal
- Mueve videos subidos a carpeta "subidos"

Uso: python src/upload_gemini_videos.py
"""

import argparse
import glob
import json
import logging
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from research import _call_groq
from publisher import upload_to_youtube, notify_telegram

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DEFAULT_FOLDER = os.path.expanduser("~/Downloads")
DEFAULT_CHANNEL = "vida_sana_360"


def convert_to_vertical(input_path: str, output_path: str) -> bool:
    """Convierte cualquier video a vertical 9:16 (1080x1920) para Shorts."""
    # Detectar dimensiones originales
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", input_path],
        capture_output=True, text=True, timeout=10,
    )
    try:
        w, h = map(int, probe.stdout.strip().split(","))
    except (ValueError, AttributeError):
        w, h = 1920, 1080  # Asumir horizontal

    if h > w:
        # Ya es vertical — solo copiar con recodificación ligera
        vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    else:
        # Horizontal → vertical: escalar y crop centrado
        vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        log.error("Error convirtiendo: %s", result.stderr[-300:])
        return False
    return True


def generate_metadata(video_filename: str, channel_config: dict) -> dict:
    """Genera título, descripción y tags relevantes al canal."""
    niche = channel_config.get("niche", "")
    name = channel_config.get("name", "")
    cta = channel_config.get("cta", "")

    # Limpiar nombre de archivo para interpretar tema
    clean_name = video_filename.replace("_", " ").replace("-", " ").replace(".mp4", "")

    prompt = f"""Eres un experto en SEO de YouTube en español. Canal: {name} | Nicho: {niche}

El video trata sobre: {clean_name}

Genera un título VIRAL para YouTube Short. El título debe:
- Generar CURIOSIDAD o URGENCIA ("El secreto que...", "Nadie te dice esto sobre...", "Haz esto CADA mañana y...")
- Incluir la PALABRA CLAVE principal del tema
- Máximo 55 caracteres
- 1 emoji al final
- NUNCA títulos genéricos como "Pérdida de peso" o "Dieta efectiva"
- SIEMPRE específico: "Pierde 3kg en 2 semanas con ESTE truco" > "Pérdida de peso"

EJEMPLOS DE TÍTULOS BUENOS:
- "Come ESTO antes de dormir y quema grasa 🔥"
- "El error #1 que arruina tu dieta sin saberlo 😱"
- "Haz esto 5 minutos al despertar y adelgaza 💪"
- "NADIE te dice esto sobre las calorías 🤯"
- "3 alimentos que DESTRUYEN tu metabolismo ❌"

Responde SOLO JSON:
{{
  "title": "título viral específico max 55 chars con emoji",
  "description": "2 líneas sobre el tema + 5 hashtags\\n\\n{cta}",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"]
}}"""
    return _call_groq(prompt, temperature=0.8)


def upload_batch(folder: str, channel_name: str):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "channels", f"{channel_name}.json")

    if not os.path.exists(config_path):
        log.error("Canal no encontrado: %s", config_path)
        return

    with open(config_path) as f:
        channel_config = json.load(f)

    videos = sorted(glob.glob(os.path.join(folder, "*.mp4")))
    if not videos:
        log.info("No hay videos .mp4 en %s", folder)
        return

    log.info("Encontrados %d videos en %s", len(videos), folder)
    uploaded = []

    for video_path in videos:
        filename = os.path.basename(video_path)
        log.info("Procesando: %s", filename)

        try:
            # 1. Convertir a vertical 9:16
            vertical_path = video_path + ".vertical.mp4"
            log.info("Convirtiendo a vertical 9:16...")
            if not convert_to_vertical(video_path, vertical_path):
                log.error("No se pudo convertir %s", filename)
                continue

            # 2. Generar metadata
            meta = generate_metadata(filename, channel_config)
            log.info("Título: %s", meta["title"])

            # 3. Subir
            url = upload_to_youtube(
                video_path=vertical_path,
                title=meta["title"],
                description=meta["description"],
                tags=meta["tags"],
                channel_config=channel_config,
            )

            uploaded.append({"file": filename, "url": url, "title": meta["title"]})

            # 4. Limpiar y mover
            os.remove(vertical_path)
            done_dir = os.path.join(folder, "subidos")
            os.makedirs(done_dir, exist_ok=True)
            os.rename(video_path, os.path.join(done_dir, filename))

            log.info("OK: %s → %s", filename, url)

        except Exception as e:
            log.error("Error con %s: %s", filename, e)
            # Limpiar temporal si existe
            if os.path.exists(video_path + ".vertical.mp4"):
                os.remove(video_path + ".vertical.mp4")

    if uploaded:
        lines = [f"📤 <b>{len(uploaded)} Shorts subidos a {channel_config['name']}</b>\n"]
        for v in uploaded:
            lines.append(f"• {v['title']}\n  {v['url']}")
        notify_telegram("\n".join(lines))
    else:
        log.info("Ningún video subido")


def main():
    parser = argparse.ArgumentParser(description="Subir videos de Gemini a YouTube como Shorts")
    parser.add_argument("--folder", default=DEFAULT_FOLDER, help="Carpeta con videos MP4")
    parser.add_argument("--channel", default=DEFAULT_CHANNEL, help="Canal destino")
    args = parser.parse_args()

    os.makedirs(args.folder, exist_ok=True)
    upload_batch(args.folder, args.channel)


if __name__ == "__main__":
    main()
