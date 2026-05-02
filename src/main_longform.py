"""
YouTube Long-Form Bot — Orquestador para videos largos.
Soporta 3 tipos:
  - lofi_music:     imagen + música looped → 1h video
  - nature_ambient: clips Pexels nature + audio ambient → 1h video
  - true_crime:     guión AI + voz inglés + B-roll → 10-15 min video

Uso: python src/main_longform.py --channel chill_orbit
"""

import argparse
import json
import logging
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from publisher import upload_to_youtube_longform, notify_telegram
from assembler_longform import assemble_lofi, assemble_nature, assemble_truecrime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("longform")

# --- AI providers (reutiliza research.py) ---
from research import _call_with_fallback


def load_channel(name: str) -> dict:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "channels", f"{name}.json")
    with open(path) as f:
        return json.load(f)


# ============================================================
# CHILL ORBIT — Lo-fi Music
# ============================================================

def run_lofi(channel: dict, work_dir: str) -> dict:
    """Genera video lo-fi: imagen Imagen4 + música de librería looped."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    duration_min = channel.get("duration_minutes", 60)

    # 1. Elegir tema
    topic = random.choice(channel["topics"])
    log.info("Tema lo-fi: %s", topic)

    # 2. Generar título y metadata con AI
    metadata = _call_with_fallback(f"""Generate metadata for a lo-fi music YouTube video.
Theme: {topic}

Respond JSON:
{{
  "title": "creative title max 60 chars, include emojis like lofi channels do",
  "description": "YouTube description 3 lines, include keywords: lofi, study, chill, relax",
  "tags": ["tag1", "tag2", ..., "tag10"]
}}""", primary="groq", temperature=0.9)

    # 3. Generar imagen de fondo con Imagen 4
    log.info("Generando imagen de fondo con Imagen 4...")
    bg_image = _generate_background_image(topic, channel, work_dir)

    # 4. Generar música con Lyria 3 Pro (o usar librería local si existe)
    music_dir = os.path.join(project_root, "assets", "music", "lofi")
    music_files = [os.path.join(music_dir, f) for f in os.listdir(music_dir)
                   if f.endswith((".mp3", ".wav", ".ogg"))] if os.path.isdir(music_dir) else []

    if music_files:
        music_track = random.choice(music_files)
        log.info("Track local: %s", os.path.basename(music_track))
    else:
        log.info("Generando track con Lyria 3 Pro...")
        music_track = _generate_lofi_track(topic, work_dir)
        log.info("Track generado: %s", os.path.basename(music_track))

    # 5. Ensamblar
    output_path = os.path.join(work_dir, "final_lofi.mp4")
    assemble_lofi(
        background_image=bg_image,
        music_path=music_track,
        duration_minutes=duration_min,
        output_path=output_path,
    )

    return {
        "video_path": output_path,
        "title": metadata["title"],
        "description": metadata["description"],
        "tags": channel.get("default_tags", []) + metadata.get("tags", []),
        "topic": topic,
    }


def _generate_lofi_track(topic: str, work_dir: str) -> str:
    """Genera track lo-fi con Lyria 3 Pro."""
    import base64
    import urllib.request

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY necesaria para Lyria")

    prompt = (
        f"lofi hip hop beat, {topic}, chill piano melody, vinyl crackle, "
        f"soft drums, warm analog sound, relaxing, study music"
    )

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["audio"]},
    }).encode()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/lyria-3-pro-preview:generateContent?key={api_key}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read())

    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        if "inlineData" in part:
            audio = base64.b64decode(part["inlineData"]["data"])
            path = os.path.join(work_dir, "lofi_track.mp3")
            with open(path, "wb") as f:
                f.write(audio)
            log.info("Lyria track: %d KB", len(audio) // 1024)
            return path

    raise RuntimeError("Lyria no devolvió audio")


def _generate_background_image(topic: str, channel: dict, work_dir: str) -> str:
    """Genera imagen aesthetic con Imagen 4."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY necesaria para generar imágenes")

    import requests as req
    import base64

    prompt = (
        f"Anime aesthetic illustration for lo-fi music video background, "
        f"theme: {topic}, cozy atmosphere, soft lighting, "
        f"{channel.get('thumbnail_style', 'purple blue gradient, night sky')}, "
        f"no text, no watermark, high quality, 4K wallpaper style"
    )

    resp = req.post(
        "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"Imagen 4 error: {data['error']['message']}")

    img_bytes = base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])
    img_path = os.path.join(work_dir, "background.png")
    with open(img_path, "wb") as f:
        f.write(img_bytes)

    log.info("Imagen generada: %s (%d KB)", img_path, len(img_bytes) // 1024)
    return img_path


# ============================================================
# CALM EARTH — Nature Ambient
# ============================================================

def run_nature(channel: dict, work_dir: str) -> dict:
    """Genera video nature: clips Pexels landscape + audio ambient."""
    duration_min = channel.get("duration_minutes", 60)

    # 1. Elegir tema
    topic = random.choice(channel["topics"])
    log.info("Tema nature: %s", topic)

    # 2. Metadata con AI
    metadata = _call_with_fallback(f"""Generate metadata for a nature ambient YouTube video.
Theme: {topic}

Respond JSON:
{{
  "title": "calming title max 60 chars with nature emoji",
  "description": "YouTube description 3 lines, keywords: nature sounds, relaxation, sleep, meditation, ASMR",
  "tags": ["tag1", "tag2", ..., "tag10"],
  "search_queries": ["pexels search query 1 in english", "query 2", "query 3", "query 4", "query 5"]
}}""", primary="groq", temperature=0.9)

    # 3. Descargar clips de Pexels (landscape, muchos)
    log.info("Descargando clips de Pexels...")
    clips = _download_nature_clips(
        metadata.get("search_queries", [topic]),
        work_dir,
        num_clips=20,
    )

    if not clips:
        raise RuntimeError("No se pudieron descargar clips de Pexels")

    log.info("Clips descargados: %d", len(clips))

    # 4. Generar thumbnail con Imagen 4
    thumbnail = None
    try:
        thumbnail = _generate_nature_thumbnail(topic, channel, work_dir)
    except Exception as e:
        log.warning("No se pudo generar thumbnail: %s", e)

    # 5. Ensamblar
    output_path = os.path.join(work_dir, "final_nature.mp4")
    assemble_nature(
        clips=clips,
        duration_minutes=duration_min,
        output_path=output_path,
    )

    return {
        "video_path": output_path,
        "title": metadata["title"],
        "description": metadata["description"],
        "tags": channel.get("default_tags", []) + metadata.get("tags", []),
        "topic": topic,
        "thumbnail": thumbnail,
    }


def _download_nature_clips(queries: list[str], work_dir: str, num_clips: int = 20) -> list[str]:
    """Descarga clips landscape de Pexels para nature ambient."""
    import requests as req

    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        raise RuntimeError("PEXELS_API_KEY necesaria")

    headers = {"Authorization": api_key}
    paths = []
    seen_ids = set()

    for query in queries:
        if len(paths) >= num_clips:
            break
        try:
            resp = req.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={
                    "query": query,
                    "per_page": 10,
                    "orientation": "landscape",
                    "size": "medium",
                },
                timeout=30,
            )
            resp.raise_for_status()

            for video in resp.json().get("videos", []):
                if len(paths) >= num_clips:
                    break
                if video["id"] in seen_ids:
                    continue
                seen_ids.add(video["id"])

                # Buscar archivo HD landscape
                best = None
                for f in video.get("video_files", []):
                    w, h = f.get("width", 0), f.get("height", 0)
                    if w > h and h >= 720:
                        if not best or abs(h - 1080) < abs(best.get("height", 0) - 1080):
                            best = f
                if not best:
                    continue

                path = os.path.join(work_dir, f"nature_{video['id']}.mp4")
                dl = req.get(best["link"], stream=True, timeout=60)
                dl.raise_for_status()
                with open(path, "wb") as out:
                    for chunk in dl.iter_content(8192):
                        out.write(chunk)
                paths.append(path)

        except Exception as e:
            log.warning("Pexels '%s': %s", query, str(e)[:80])

    return paths


def _generate_nature_thumbnail(topic: str, channel: dict, work_dir: str) -> str:
    """Genera thumbnail cinematográfico con Imagen 4."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    import requests as req
    import base64

    prompt = (
        f"Cinematic nature photograph, {topic}, "
        f"golden hour lighting, dramatic landscape, "
        f"National Geographic style, no text, no watermark, ultra HD"
    )

    resp = req.post(
        "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        return None

    img_bytes = base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])
    path = os.path.join(work_dir, "thumbnail.png")
    with open(path, "wb") as f:
        f.write(img_bytes)
    return path


# ============================================================
# DARK FILES — True Crime
# ============================================================

def run_truecrime(channel: dict, work_dir: str) -> dict:
    """Genera video true crime: guión AI + voz inglés + B-roll Pexels."""
    duration_min = channel.get("duration_minutes", 12)

    # 1. Elegir tema
    topic = random.choice(channel["topics"])
    log.info("Tema true crime: %s", topic)

    # 2. Generar guión completo con AI
    log.info("Generando guión...")
    script = _call_with_fallback(f"""You are a true crime documentary scriptwriter for YouTube.
Write a compelling 10-minute narration script about: {topic}

RULES:
- Write in English
- Start with a gripping hook
- Use suspenseful, investigative tone like Netflix documentaries
- Include real-sounding details (locations, dates, names)
- Break into 15-20 segments for natural pauses
- Each segment = 30-45 seconds of narration
- End with a thought-provoking conclusion + subscribe CTA

Respond JSON:
{{
  "title": "compelling title max 60 chars, dark/mysterious tone",
  "description": "YouTube description 3 lines with true crime keywords",
  "tags": ["true crime", "mystery", "unsolved", ...8 more],
  "case_name": "short case reference",
  "segments": [
    {{"voice": "narration text for this segment", "visual": "B-roll description for Pexels search", "duration": 35}},
    ...
  ],
  "thumbnail_text": "2-3 word dramatic text for thumbnail"
}}""", primary="github", temperature=0.7)

    # 3. Generar voz en inglés con Edge TTS
    log.info("Generando voz inglés...")
    voice_id = channel.get("voice", "en-US-GuyNeural")
    voiced = _generate_english_voice(script["segments"], work_dir, voice_id)

    # 4. Descargar B-roll de Pexels
    log.info("Descargando B-roll...")
    visuals = list({s.get("visual", "dark city night") for s in script["segments"]})
    clips = _download_nature_clips(visuals[:8], work_dir, num_clips=15)

    if not clips:
        # Fallback genérico
        clips = _download_nature_clips(
            ["dark city night", "foggy forest", "detective office", "police lights", "old documents"],
            work_dir, num_clips=10,
        )

    # 5. Generar thumbnail
    thumbnail = None
    try:
        thumbnail = _generate_truecrime_thumbnail(script, channel, work_dir)
    except Exception as e:
        log.warning("Thumbnail error: %s", e)

    # 6. Ensamblar
    output_path = os.path.join(work_dir, "final_truecrime.mp4")
    assemble_truecrime(
        clips=clips,
        voiced_segments=voiced,
        output_path=output_path,
    )

    return {
        "video_path": output_path,
        "title": script["title"],
        "description": script["description"],
        "tags": channel.get("default_tags", []) + script.get("tags", []),
        "topic": f"{topic} — {script.get('case_name', '')}",
        "thumbnail": thumbnail,
    }


def _generate_english_voice(segments: list[dict], work_dir: str, voice_id: str) -> list[dict]:
    """Genera voz en inglés con Edge TTS."""
    import asyncio
    import edge_tts
    import subprocess

    results = []
    for i, seg in enumerate(segments):
        text = seg["voice"]
        audio_path = os.path.join(work_dir, f"voice_{i}.mp3")

        try:
            communicate = edge_tts.Communicate(text, voice_id, rate="-5%")
            asyncio.run(communicate.save(audio_path))

            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, text=True, timeout=10,
            )
            duration = float(probe.stdout.strip()) if probe.stdout.strip() else seg.get("duration", 30)

            results.append({
                "voice": text,
                "audio_path": audio_path,
                "duration": max(duration, 2.0),
                "visual": seg.get("visual", ""),
            })
        except Exception as e:
            log.warning("TTS segment %d error: %s", i, str(e)[:80])
            results.append({
                "voice": text,
                "audio_path": None,
                "duration": seg.get("duration", 30),
                "visual": seg.get("visual", ""),
            })

    return results


def _generate_truecrime_thumbnail(script: dict, channel: dict, work_dir: str) -> str:
    """Genera thumbnail oscuro/misterioso con Imagen 4."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    import requests as req
    import base64

    text_overlay = script.get("thumbnail_text", "DARK FILES")
    prompt = (
        f"Dark dramatic YouTube thumbnail, true crime documentary style, "
        f"text overlay says '{text_overlay}', "
        f"dark moody lighting, red accent, noir atmosphere, "
        f"cinematic composition, no watermark"
    )

    resp = req.post(
        "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "16:9"},
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        return None

    img_bytes = base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])
    path = os.path.join(work_dir, "thumbnail.png")
    with open(path, "wb") as f:
        f.write(img_bytes)
    return path


# ============================================================
# ORQUESTADOR
# ============================================================

RUNNERS = {
    "lofi_music": run_lofi,
    "nature_ambient": run_nature,
    "true_crime": run_truecrime,
}


def run(channel_name: str):
    channel = load_channel(channel_name)
    content_type = channel.get("content_type")
    runner = RUNNERS.get(content_type)

    if not runner:
        raise ValueError(f"content_type '{content_type}' no soportado. Usa: {list(RUNNERS.keys())}")

    work_dir = tempfile.mkdtemp(prefix=f"ytbot_lf_{channel_name}_")

    log.info("=" * 60)
    log.info("Canal: %s | Tipo: %s", channel["name"], content_type)
    log.info("=" * 60)

    # Generar video
    result = runner(channel, work_dir)

    video_path = result["video_path"]
    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    log.info("Video final: %.1f MB", size_mb)

    # Subir a YouTube
    log.info("Subiendo a YouTube...")
    video_url = upload_to_youtube_longform(
        video_path=video_path,
        title=result["title"],
        description=result["description"],
        tags=result["tags"],
        channel_config=channel,
        thumbnail_path=result.get("thumbnail"),
    )

    # Telegram
    msg = (
        f"🎬 <b>{channel['name']}</b> (Long-form)\n\n"
        f"📹 {result['title']}\n"
        f"🔗 {video_url}\n\n"
        f"📊 Tema: {result['topic']}\n"
        f"📦 {size_mb:.1f} MB"
    )
    notify_telegram(msg)

    log.info("Completado: %s", video_url)
    return video_url


def main():
    parser = argparse.ArgumentParser(description="YouTube Long-Form Bot")
    parser.add_argument("--channel", required=True)
    args = parser.parse_args()

    try:
        url = run(args.channel)
        print(f"\nVideo: {url}")
    except Exception as e:
        log.error("Error: %s", e, exc_info=True)
        try:
            notify_telegram(f"❌ <b>Error en {args.channel}</b> (longform)\n\n{str(e)[:500]}")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
