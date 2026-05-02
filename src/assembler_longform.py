"""
Ensamblaje de videos long-form (16:9 landscape).
Tres modos:
  - Lo-fi: imagen estática con zoom lento + música looped
  - Nature: clips Pexels concatenados con su propio audio
  - True Crime: clips de fondo + voz narrada
"""

import logging
import os
import subprocess
import tempfile

log = logging.getLogger(__name__)

WIDTH = 1920
HEIGHT = 1080


def _run_ffmpeg(cmd: list[str], timeout: int = 3600):
    """Ejecuta FFmpeg con manejo de errores."""
    log.info("FFmpeg: %s", " ".join(cmd[:8]) + "...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        log.error("FFmpeg error: %s", result.stderr[-500:])
        raise RuntimeError(f"FFmpeg falló: {result.stderr[-300:]}")
    return result


def _get_duration(path: str) -> float:
    """Duración de un archivo multimedia."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, timeout=10,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


# ============================================================
# LO-FI: imagen + música looped
# ============================================================

def assemble_lofi(
    background_image: str,
    music_path: str,
    duration_minutes: int,
    output_path: str,
):
    """Crea video lo-fi: imagen con zoom/pan sutil + música en loop."""
    duration_sec = duration_minutes * 60
    music_dur = _get_duration(music_path)

    if music_dur <= 0:
        raise RuntimeError(f"Track de música inválido: {music_path}")

    log.info("Ensamblando lo-fi: %d min, track %.0fs (se loopea)", duration_minutes, music_dur)

    # Imagen estática + música looped — sin zoompan pesado
    # Usar framerate bajo (1fps) con imagen estática = encoding rapidísimo
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "1", "-i", background_image,
        "-stream_loop", "-1", "-i", music_path,
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration_sec),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-r", "1",
        output_path,
    ]

    _run_ffmpeg(cmd, timeout=900)
    log.info("Lo-fi video ensamblado: %s", output_path)


# ============================================================
# NATURE: clips concatenados con audio propio
# ============================================================

def assemble_nature(
    clips: list[str],
    duration_minutes: int,
    output_path: str,
):
    """Crea video nature: clips landscape looped hasta duración target."""
    duration_sec = duration_minutes * 60
    work_dir = tempfile.mkdtemp(prefix="ytbot_nature_")

    # 1. Procesar clips a formato uniforme (1920x1080, 24fps, ultrafast)
    processed = []
    for i, clip in enumerate(clips):
        out = os.path.join(work_dir, f"proc_{i}.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", clip,
            "-vf", (
                f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},setsar=1"
            ),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26",
            "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-ac", "2",
            "-r", "24", "-t", "30",
            out,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                processed.append(out)
            else:
                log.warning("Error clip %d: %s", i, result.stderr[-80:])
        except subprocess.TimeoutExpired:
            log.warning("Timeout clip %d, saltando", i)

    if not processed:
        raise RuntimeError("No se pudo procesar ningún clip")

    # 2. Calcular duración total de clips
    total_clip_dur = sum(_get_duration(p) for p in processed)
    log.info("Clips procesados: %d, duración total: %.0fs", len(processed), total_clip_dur)

    # 3. Crear lista de concatenación (repitiendo clips hasta cubrir duración)
    concat_list = os.path.join(work_dir, "concat.txt")
    with open(concat_list, "w") as f:
        accumulated = 0.0
        while accumulated < duration_sec:
            for clip in processed:
                f.write(f"file '{clip}'\n")
                accumulated += _get_duration(clip)
                if accumulated >= duration_sec:
                    break

    # 4. Concatenar clips
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(duration_sec),
        "-movflags", "+faststart",
        output_path,
    ]

    _run_ffmpeg(cmd, timeout=3600)
    log.info("Nature video ensamblado: %s", output_path)


# ============================================================
# TRUE CRIME: clips + voz narrada
# ============================================================

def assemble_truecrime(
    clips: list[str],
    voiced_segments: list[dict],
    output_path: str,
):
    """Crea video true crime: B-roll + narración en inglés."""
    work_dir = tempfile.mkdtemp(prefix="ytbot_crime_")

    # 1. Concatenar todos los audios de voz
    voice_path = os.path.join(work_dir, "voice_full.mp3")
    total_duration = _concat_voice_segments(voiced_segments, voice_path, work_dir)
    log.info("Voz total: %.0fs", total_duration)

    # 2. Procesar clips de fondo a formato uniforme
    processed = []
    for i, clip in enumerate(clips):
        out = os.path.join(work_dir, f"proc_{i}.mp4")
        cmd = [
            "ffmpeg", "-y", "-i", clip,
            "-vf", (
                f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},setsar=1"
            ),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
            "-an", "-r", "24",
            out,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            processed.append(out)

    if not processed:
        raise RuntimeError("No se pudo procesar ningún clip de B-roll")

    # 3. Concatenar clips en loop hasta cubrir duración del audio
    bg_video = os.path.join(work_dir, "background.mp4")
    concat_list = os.path.join(work_dir, "concat.txt")
    with open(concat_list, "w") as f:
        accumulated = 0.0
        while accumulated < total_duration + 5:
            for clip in processed:
                f.write(f"file '{clip}'\n")
                accumulated += _get_duration(clip)
                if accumulated >= total_duration + 5:
                    break

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:v", "copy",
        "-an",
        "-t", str(int(total_duration) + 3),
        bg_video,
    ]
    _run_ffmpeg(cmd, timeout=1800)

    # 4. Combinar video + voz
    cmd = [
        "ffmpeg", "-y",
        "-i", bg_video,
        "-i", voice_path,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(int(total_duration) + 2),
        "-movflags", "+faststart",
        output_path,
    ]
    _run_ffmpeg(cmd, timeout=600)
    log.info("True crime video ensamblado: %s (%.0fs)", output_path, total_duration)


def _concat_voice_segments(segments: list[dict], output: str, work_dir: str) -> float:
    """Concatena segmentos de voz con pausas breves."""
    valid = [s for s in segments if s.get("audio_path") and os.path.exists(s["audio_path"])]
    if not valid:
        raise RuntimeError("No hay segmentos de voz válidos")

    # Crear pausa de 0.8s entre segmentos
    pause_path = os.path.join(work_dir, "pause.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", "0.8", "-c:a", "libmp3lame", pause_path],
        capture_output=True, text=True, timeout=10,
    )

    concat_list = os.path.join(work_dir, "voice_list.txt")
    with open(concat_list, "w") as f:
        for seg in valid:
            f.write(f"file '{seg['audio_path']}'\n")
            f.write(f"file '{pause_path}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        "-c:a", "libmp3lame", "-b:a", "192k", output,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)

    return _get_duration(output)
