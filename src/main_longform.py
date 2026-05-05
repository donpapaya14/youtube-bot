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
    """Genera video lo-fi: imagen Pexels + música local looped. 100% gratis."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    duration_min = channel.get("duration_minutes", 60)

    # 1. Elegir tema
    topic = random.choice(channel["topics"])
    log.info("Tema lo-fi: %s", topic)

    # 2. Generar título y metadata con AI (gratis: Groq/GitHub/NVIDIA)
    metadata = _call_with_fallback(f"""Generate metadata for a lo-fi music YouTube video.
Theme: {topic}

Respond JSON:
{{
  "title": "creative title max 60 chars, include emojis like lofi channels do",
  "description": "YouTube description 3 lines, include keywords: lofi, study, chill, relax",
  "tags": ["tag1", "tag2", ..., "tag10"]
}}""", primary="groq", temperature=0.9)

    # 3. Imagen de fondo: intenta Imagen 4 (gratis tier), fallback Pexels
    log.info("Obteniendo imagen de fondo...")
    bg_image = _get_background_image(topic, channel, work_dir)

    # 4. Música: librería local primero, Lyria gratis como fallback
    music_dir = os.path.join(project_root, "assets", "music", "lofi")
    music_files = [os.path.join(music_dir, f) for f in os.listdir(music_dir)
                   if f.endswith((".mp3", ".wav", ".ogg"))] if os.path.isdir(music_dir) else []

    if music_files:
        music_track = random.choice(music_files)
        log.info("Track local: %s", os.path.basename(music_track))
    else:
        log.info("Sin tracks locales, intentando Lyria (tier gratis)...")
        music_track = _generate_lofi_track_free(topic, work_dir)

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


def _get_background_image(topic: str, channel: dict, work_dir: str) -> str:
    """Intenta Imagen 4 (tier gratis), fallback a Pexels."""
    # Intentar Imagen 4 primero (gratis hasta cierta cuota)
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
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
                json={"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "16:9"}},
                timeout=120,
            )
            data = resp.json()
            if "predictions" in data:
                img_bytes = base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])
                path = os.path.join(work_dir, "background.png")
                with open(path, "wb") as f:
                    f.write(img_bytes)
                log.info("Imagen 4 (gratis): %d KB", len(img_bytes) // 1024)
                return path
            log.warning("Imagen 4 sin cuota gratis, usando Pexels")
        except Exception as e:
            log.warning("Imagen 4 fallback: %s", str(e)[:80])

    # Fallback: Pexels (siempre gratis)
    return _download_pexels_image(topic, work_dir)


def _download_pexels_image(topic: str, work_dir: str) -> str:
    """Descarga imagen de fondo de Pexels (gratis)."""
    import requests as req

    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        raise RuntimeError("PEXELS_API_KEY necesaria")

    search = f"{topic} aesthetic background"
    resp = req.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": api_key},
        params={"query": search, "per_page": 15, "orientation": "landscape"},
        timeout=30,
    )
    resp.raise_for_status()
    photos = resp.json().get("photos", [])

    if not photos:
        resp = req.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": api_key},
            params={"query": "cozy night aesthetic", "per_page": 10, "orientation": "landscape"},
            timeout=30,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])

    if not photos:
        raise RuntimeError("No se encontraron imágenes en Pexels")

    photo = random.choice(photos)
    img_url = photo["src"]["large2x"]
    dl = req.get(img_url, timeout=30)
    dl.raise_for_status()
    path = os.path.join(work_dir, "background.jpg")
    with open(path, "wb") as f:
        f.write(dl.content)
    log.info("Imagen Pexels: %s (%d KB)", photo.get("alt", "")[:40], len(dl.content) // 1024)
    return path


def _generate_lofi_track_free(topic: str, work_dir: str) -> str:
    """Genera track con Lyria (tier gratis). Falla si no hay cuota."""
    import base64
    import urllib.request

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Sin tracks locales ni GEMINI_API_KEY. Pon MP3s en assets/music/lofi/")

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
            log.info("Lyria track (gratis): %d KB", len(audio) // 1024)
            return path

    raise RuntimeError("Lyria sin cuota gratis disponible")


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

    # 4. Ensamblar (sin thumbnail de pago)
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

    # 1. Intentar script pre-escrito
    script = _load_prewritten_script(channel)
    if script:
        log.info("Usando guión pre-escrito: %s", script.get("title", "?"))
    else:
        # Elegir tema y generar con AI
        topic = random.choice(channel["topics"])
        log.info("Tema true crime: %s", topic)

    # 2. Generar guión completo con AI si no hay pre-escrito
    if not script:
        log.info("Generando guión con AI...")
        for attempt in range(3):
            script = _call_with_fallback(f"""You are a true crime documentary scriptwriter for YouTube.
Write a LONG, detailed 15-minute narration script about: {topic}

LEGAL & ETHICAL RULES (MANDATORY):
- ONLY narrate REAL, DOCUMENTED cases from public records
- NEVER invent names, dates, locations, or details
- For each case, mention the SOURCE: news outlet, court documents, police reports, or official investigations
- Use phrases like "According to police reports...", "Court documents reveal...", "As reported by [news outlet]..."
- If details are uncertain, say "allegedly", "reportedly", "according to witnesses"
- Do NOT accuse anyone who was not convicted — always say "suspect" or "person of interest" for unconvicted individuals
- Include a disclaimer reference: "This story is based on publicly available information"
- Respect victims — do not sensationalize graphic details unnecessarily

CONTENT REQUIREMENTS:
- You MUST write EXACTLY 30 segments. COUNT THEM: 1, 2, 3... 30.
- Each segment MUST have 4-6 sentences of narration (60-100 words each)
- Total narration MUST be 2000-2500 words minimum
- Write in English
- Start with a gripping hook that makes viewers stay
- Use suspenseful, investigative tone like Netflix true crime documentaries
- Build tension gradually — each segment reveals something new
- Include forensic evidence details, witness testimony, investigation timeline
- End with current case status + "If you have information, contact..." + "Subscribe for more cases"

STRUCTURE (30 segments):
1-3: Hook + case intro + "This story is based on publicly available court and police records"
4-8: Victim background + events leading up
9-14: The crime itself + immediate aftermath + first responders
15-20: Investigation details + evidence + suspects + forensic analysis
21-26: Twists, new evidence, theories, trial proceedings
27-30: Verdict or current status + lasting impact + CTA

Respond JSON:
{{
  "title": "compelling title max 60 chars, dark/mysterious tone",
  "description": "YouTube description with: case summary, sources referenced, true crime keywords, disclaimer: Based on publicly available information from court records and news reports",
  "tags": ["true crime", "mystery", "unsolved", "cold case", "crime documentary", "investigation", "dark files", "criminal", "detective", "forensic"],
  "case_name": "real case name or reference",
  "sources": ["source 1: news outlet or court record", "source 2"],
  "segments": [
    {{"voice": "LONG narration 4-6 sentences, 60-100 words, citing sources where relevant", "visual": "B-roll description for Pexels search", "duration": 30}},
    ... (EXACTLY 30 segments, no less)
  ],
  "thumbnail_text": "2-3 word dramatic text for thumbnail"
}}""", primary="github", temperature=0.7)

            num_segs = len(script.get("segments", []))
            total_words = sum(len(s.get("voice", "").split()) for s in script.get("segments", []))
            log.info("Guión intento %d: %d segmentos, %d palabras", attempt + 1, num_segs, total_words)

            if num_segs >= 20 and total_words >= 1500:
                break
            log.warning("Guión muy corto (%d segs, %d words), reintentando...", num_segs, total_words)

    if len(script.get("segments", [])) < 15:
        raise RuntimeError(f"Guión demasiado corto: {len(script.get('segments', []))} segmentos")

    # Añadir fuentes a la descripción
    sources = script.get("sources", [])
    if sources:
        source_text = "\n".join(f"• {s}" for s in sources[:5])
        script["description"] += f"\n\nSources:\n{source_text}\n\nDisclaimer: Based on publicly available information from court records, police reports, and news coverage."
    else:
        script["description"] += "\n\nDisclaimer: Based on publicly available information from court records, police reports, and news coverage."

    # 3. Generar voz en inglés con Edge TTS
    log.info("Generando voz inglés...")
    voice_id = channel.get("voice", "en-US-GuyNeural")
    voiced = _generate_english_voice(script["segments"], work_dir, voice_id)

    # 4. Descargar B-roll de Pexels (filtrar contenido sensible)
    log.info("Descargando B-roll...")
    _BANNED_TERMS = {"covid", "coronavirus", "pandemic", "vaccine", "mask", "hospital patient", "icu", "ventilator"}
    visuals = [s.get("visual", "dark city night") for s in script["segments"]]
    visuals = list({v for v in visuals if not any(b in v.lower() for b in _BANNED_TERMS)})
    clips = _download_nature_clips(visuals[:8], work_dir, num_clips=15)

    if not clips:
        clips = _download_nature_clips(
            ["dark city night", "foggy forest", "detective noir", "old typewriter documents", "abandoned building"],
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
        "topic": script.get("title", ""),
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
# NARRATED EDUCATIONAL — Documentales educativos en español
# ============================================================

def run_narrated_educational(channel: dict, work_dir: str) -> dict:
    """Genera documental educativo: guión pre-escrito o AI + voz español + B-roll Pexels."""
    duration_min = channel.get("duration_minutes", 12)

    # 1. Intentar script pre-escrito primero
    script = _load_prewritten_script(channel)

    if script:
        log.info("Usando guión pre-escrito: %s", script.get("title", "?"))
    else:
        # 2. Elegir tema y generar con AI
        topic = random.choice(channel["topics"])
        log.info("Tema educativo: %s", topic)

        niche = channel.get("niche", "educación")
        tone = channel.get("tone", "informativo")
        lang = channel.get("language", "es")
        target_segments = max(25, duration_min * 2)
        target_words = max(1800, duration_min * 150)

        for attempt in range(3):
            script = _call_with_fallback(f"""Eres un guionista de documentales educativos para YouTube en español.
Canal: {channel['name']} | Nicho: {niche}
Tono: {tone}

CREA UN DOCUMENTAL COMPLETO SOBRE: {topic}

REQUISITOS DE CONTENIDO:
- OBLIGATORIO: {target_segments} segmentos mínimo
- Cada segmento: 3-5 frases de narración (50-80 palabras)
- Total: {target_words}+ palabras de narración
- TODO real y VERIFICABLE — cita estudios, universidades, fuentes reales
- Si mencionas un dato, di DE DÓNDE viene (universidad, estudio, año)
- Lenguaje {'en español' if lang == 'es' else 'en inglés'}, accesible, sin tecnicismos innecesarios

ESTRUCTURA:
1-3: Gancho impactante + dato que sorprenda + contexto del tema
4-8: Desarrollo principal — datos, estudios, explicaciones
9-14: Profundización — casos reales, ejemplos prácticos
15-20: Más evidencia, contrastes, mitos vs realidad
21-{target_segments}: Conclusiones prácticas + CTA potente

ÚLTIMO SEGMENTO: CTA con urgencia — "Si esto te ha parecido útil, lo que viene la próxima semana te va a sorprender. Suscríbete para no perdértelo."

Responde JSON:
{{
  "title": "título SEO max 60 chars, con 1 emoji relevante",
  "description": "descripción YouTube 3-4 líneas con keywords naturales, fuentes mencionadas, y CTA al canal",
  "tags": ["tag1", "tag2", ..., "tag10"],
  "segments": [
    {{"voice": "narración completa 3-5 frases con datos reales", "visual": "descripción visual para B-roll en inglés (búsqueda Pexels)", "duration": 25}},
    ... (mínimo {target_segments} segmentos)
  ],
  "thumbnail_text": "2-3 palabras impactantes para thumbnail"
}}""", primary="github", temperature=0.7)

            num_segs = len(script.get("segments", []))
            total_words = sum(len(s.get("voice", "").split()) for s in script.get("segments", []))
            log.info("Guión intento %d: %d segmentos, %d palabras", attempt + 1, num_segs, total_words)

            if num_segs >= 20 and total_words >= 1500:
                break
            log.warning("Guión corto (%d segs, %d words), reintentando...", num_segs, total_words)

    if len(script.get("segments", [])) < 15:
        raise RuntimeError(f"Guión demasiado corto: {len(script.get('segments', []))} segmentos")

    # Añadir CTA del canal a la descripción
    cta = channel.get("cta_description", "")
    script["description"] = script.get("description", "") + cta

    # 3. Generar voz en español con Edge TTS
    log.info("Generando voz...")
    voice_id = channel.get("voice", "es-ES-AlvaroNeural")
    voiced = _generate_english_voice(script["segments"], work_dir, voice_id)

    # 4. Descargar B-roll de Pexels
    log.info("Descargando B-roll...")
    _BANNED_TERMS = {"covid", "coronavirus", "pandemic", "vaccine", "mask", "hospital patient", "icu", "ventilator"}
    visuals = [s.get("visual", "educational documentary") for s in script["segments"]]
    visuals = list({v for v in visuals if not any(b in v.lower() for b in _BANNED_TERMS)})
    clips = _download_nature_clips(visuals[:10], work_dir, num_clips=15)

    if not clips:
        clips = _download_nature_clips(
            ["educational documentary", "science laboratory", "nature landscape", "city aerial", "people lifestyle"],
            work_dir, num_clips=10,
        )

    # 5. Thumbnail
    thumbnail = None
    try:
        thumbnail = _generate_educational_thumbnail(script, channel, work_dir)
    except Exception as e:
        log.warning("Thumbnail error: %s", e)

    # 6. Ensamblar (reutiliza assembler de true crime — misma estructura)
    output_path = os.path.join(work_dir, "final_educational.mp4")
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
        "topic": script.get("title", ""),
        "thumbnail": thumbnail,
    }


def _load_prewritten_script(channel: dict) -> dict | None:
    """Carga un guión pre-escrito no usado, comprobando contra títulos de YouTube."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Mapear nombre de canal a directorio de scripts
    name_map = {
        "SaludLongevidad": "salud_longevidad",
        "CatBrothers": "catbrothers",
        "FinanzasClara": "finanzas_clara",
        "DarkFiles": "dark_files",
        "DisasterDecode": "disaster_decode",
        "MindWired": "mind_wired",
        "CashCafe": "cash_cafe",
        "EspacioInteligente": "hogarinteligente",
        "VidaSana360": "vidasana360",
    }
    dir_name = name_map.get(channel["name"], channel["name"].lower())
    scripts_dir = os.path.join(project_root, "scripts", dir_name)

    if not os.path.isdir(scripts_dir):
        return None

    # Obtener títulos recientes de YouTube para evitar duplicados
    recent_titles = []
    try:
        from research import _get_recent_titles
        recent_titles = _get_recent_titles(channel)
    except Exception as e:
        log.warning("No se pudieron obtener títulos recientes: %s", str(e)[:100])
    recent_lower = {t.lower().strip() for t in recent_titles}

    # Recorrer scripts disponibles, saltar los que ya están en YouTube
    all_scripts = sorted(f for f in os.listdir(scripts_dir) if f.endswith(".json"))

    for script_file in all_scripts:
        path = os.path.join(scripts_dir, script_file)
        with open(path) as f:
            script = json.load(f)

        title = script.get("title", "").lower().strip()
        if title in recent_lower:
            log.info("Script %s ya subido ('%s'), saltando", script_file, script.get("title", "?"))
            continue

        log.info("Guión pre-escrito cargado: %s (%d segmentos)", script_file, len(script.get("segments", [])))
        return script

    log.info("Todos los guiones pre-escritos ya subidos para %s, usando AI", channel["name"])
    return None


def _generate_educational_thumbnail(script: dict, channel: dict, work_dir: str) -> str:
    """Genera thumbnail educativo con Imagen 4."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    import requests as req
    import base64

    text_overlay = script.get("thumbnail_text", channel["name"])
    style = channel.get("thumbnail_style", "clean educational")
    prompt = (
        f"Professional YouTube thumbnail, {style}, "
        f"bold text overlay says '{text_overlay}', "
        f"eye-catching, clean design, no watermark, HD"
    )

    try:
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
        if "predictions" in data:
            img_bytes = base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])
            path = os.path.join(work_dir, "thumbnail.png")
            with open(path, "wb") as f:
                f.write(img_bytes)
            return path
    except Exception as e:
        log.warning("Thumbnail Imagen 4: %s", str(e)[:80])
    return None


# ============================================================
# ORQUESTADOR
# ============================================================

RUNNERS = {
    "lofi_music": run_lofi,
    "nature_ambient": run_nature,
    "true_crime": run_truecrime,
    "narrated_educational": run_narrated_educational,
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
