"""
Ensamblaje de YouTube Short con VOZ + TEXTO + VIDEO.
- Clips de fondo con zoom/pan
- Voz IA narrando (Edge TTS)
- Texto en pantalla sincronizado con voz
- Música de fondo baja
"""

import logging
import os
import platform
import random
import re
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

WIDTH = 1080
HEIGHT = 1920


def assemble_video(
    clips: list[str],
    voiced_segments: list[dict],
    style: dict,
    output_path: str,
    music_path: str | None = None,
    no_voice: bool = False,
) -> str:
    work_dir = tempfile.mkdtemp(prefix="ytbot_")

    # 1. Procesar clips
    processed = _process_clips(clips, work_dir)
    if not processed:
        raise RuntimeError("No hay clips procesados")

    # 2. Concatenar clips de fondo
    concat_path = os.path.join(work_dir, "concat.mp4")
    _concat_clips(processed, concat_path)

    # 3. Audio: voz TTS o silencio
    if no_voice:
        total_duration = min(sum(s.get("duration", 4.0) for s in voiced_segments), 58.0)
        voice_path = None
        log.info("Sin voz: duración total %.0fs", total_duration)
    else:
        voice_path = os.path.join(work_dir, "voice_full.mp3")
        total_duration = _concat_voice(voiced_segments, voice_path)

    # 4. Generar PNGs de texto
    slide_pngs = _generate_slide_pngs(voiced_segments, style, work_dir)

    # 5. Componer todo: video + texto overlay + música (± voz)
    _compose_final(concat_path, voice_path, slide_pngs, voiced_segments,
                   total_duration, output_path, music_path, no_voice=no_voice)

    log.info("Video ensamblado: %s", output_path)
    return output_path


def _process_clips(clips: list[str], work_dir: str) -> list[str]:
    processed = []
    for i, clip in enumerate(clips):
        out = os.path.join(work_dir, f"proc_{i}.mp4")
        bright = round(random.uniform(-0.02, 0.02), 3)
        sat = round(random.uniform(0.98, 1.04), 3)

        cmd = [
            "ffmpeg", "-y", "-i", clip,
            "-vf", (
                f"scale={WIDTH+40}:{HEIGHT+70}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},setsar=1,"
                f"eq=brightness={bright}:saturation={sat}"
            ),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(random.randint(19, 22)),
            "-an", "-r", "30", "-t", "12",
            out,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            processed.append(out)
        else:
            log.warning("Error clip %d: %s", i, result.stderr[-200:])
    return processed


def _concat_clips(clips: list[str], output: str):
    list_file = output + ".txt"
    with open(list_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-r", "30",
        output,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)


def _concat_voice(segments: list[dict], output: str) -> float:
    """Concatena audios de voz. Devuelve duración total."""
    work_dir = os.path.dirname(output)
    list_file = os.path.join(work_dir, "voice_list.txt")

    valid_segments = [s for s in segments if s.get("audio_path") and os.path.exists(s["audio_path"])]
    if not valid_segments:
        # Generar silencio si no hay voz
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "25", output]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return 25.0

    # Añadir breve pausa entre segmentos
    pause_path = os.path.join(work_dir, "pause.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.3",
         "-c:a", "libmp3lame", pause_path],
        capture_output=True, text=True, timeout=10,
    )

    with open(list_file, "w") as f:
        for seg in valid_segments:
            f.write(f"file '{seg['audio_path']}'\n")
            f.write(f"file '{pause_path}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
        "-c:a", "libmp3lame", "-b:a", "192k", output,
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)

    # Obtener duración total
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", output],
        capture_output=True, text=True, timeout=10,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return sum(s["duration"] for s in segments)


def _generate_slide_pngs(segments: list[dict], style: dict, work_dir: str) -> list[str]:
    font_path = _find_font()
    font_size = style.get("font_size", 58)
    bg_rgb = _hex_to_rgb(style.get("primary_color", "#1A1A1A"))
    txt_rgb = _hex_to_rgb(style.get("text_color", "#FFFFFF"))
    box_opacity = int(style.get("box_opacity", 0.85) * 255)

    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    paths = []
    for i, seg in enumerate(segments):
        png_path = os.path.join(work_dir, f"slide_{i}.png")
        text = _strip_emojis(seg.get("text", ""))
        if not text:
            text = _strip_emojis(seg.get("voice", ""))[:25]

        _render_slide(text, font, font_size, bg_rgb, box_opacity, txt_rgb, png_path, i, len(segments))
        paths.append(png_path)
    return paths


def _render_slide(text, font, font_size, bg_rgb, bg_opacity, txt_rgb, output, idx, total):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    lines = _wrap_text(text, 16)
    line_h = font_size + 24
    block_h = len(lines) * line_h + 56
    widths = [draw.textbbox((0, 0), l, font=font)[2] - draw.textbbox((0, 0), l, font=font)[0] for l in lines]
    block_w = min(max(widths, default=200) + 100, int(WIDTH * 0.85))

    box_x = (WIDTH - block_w) / 2
    box_y = HEIGHT * 0.38

    # Fondo
    draw.rounded_rectangle([box_x, box_y, box_x + block_w, box_y + block_h], radius=28, fill=bg_rgb + (bg_opacity,))

    # Barra progreso
    progress = (idx + 1) / total
    draw.rounded_rectangle([60, 120, 60 + int((WIDTH - 120) * progress), 128], radius=4, fill=txt_rgb + (100,))
    draw.rounded_rectangle([60, 120, WIDTH - 60, 128], radius=4, fill=(255, 255, 255, 30))

    # Texto
    for j, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        tx = (WIDTH - tw) / 2
        ty = box_y + 28 + j * line_h
        draw.text((tx + 3, ty + 3), line, font=font, fill=(0, 0, 0, 200))
        draw.text((tx, ty), line, font=font, fill=txt_rgb + (255,))

    img.save(output, "PNG")


def _compose_final(bg_video, voice_path, slide_pngs, segments, total_duration, output, music_path, no_voice=False):
    """Compone: video looped + overlay texto + música (± voz TTS)."""
    inputs = ["-stream_loop", "-1", "-i", bg_video]  # 0: video

    # 1: voz (solo si hay voz)
    if voice_path is not None:
        inputs += ["-i", voice_path]
        png_start_idx = 2
    else:
        png_start_idx = 1

    for png in slide_pngs:
        inputs += ["-i", png]  # png_start_idx+: slides

    # Overlay de texto sincronizado
    filters = []
    current_time = 0.0
    for i, seg in enumerate(segments):
        dur = seg.get("duration", 4.0)
        start = current_time
        end = current_time + dur
        src = f"[v{i}]" if i > 0 else "[0:v]"
        dst = f"[v{i+1}]"
        img_idx = i + png_start_idx
        filters.append(
            f"{src}[{img_idx}:v]overlay=0:0:enable='between(t,{start:.1f},{end:.1f})'{dst}"
        )
        current_time = end

    last_video = f"[v{len(segments)}]"
    fade_st = max(total_duration - 2, 0)

    # Audio
    if music_path and os.path.exists(music_path):
        music_idx = png_start_idx + len(slide_pngs)
        inputs += ["-i", music_path]
        if no_voice:
            # Solo música, volumen alto
            filters.append(f"[{music_idx}:a]volume=0.75,afade=t=out:st={fade_st:.1f}:d=2[aout]")
        else:
            # Voz al 100% + música al 12%
            filters.append(f"[{music_idx}:a]volume=0.12,afade=t=out:st={fade_st:.1f}:d=2[mus]")
            filters.append(f"[1:a][mus]amix=inputs=2:duration=first:dropout_transition=2[aout]")
    elif voice_path is not None:
        filters.append("[1:a]acopy[aout]")
    else:
        # Sin voz, sin música: silencio
        filters.append(f"anullsrc=r=44100:cl=mono[aout]")

    filter_str = ";".join(filters)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", last_video,
        "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-r", "30",
        "-t", str(min(total_duration, 58)),
        "-movflags", "+faststart",
        output,
    ]

    log.info("Compose: %d segs, %.0fs, con voz", len(segments), total_duration)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        log.error("FFmpeg: %s", result.stderr[-800:])
        raise RuntimeError(f"Error composición: {result.stderr[-500:]}")


def generate_shorts_thumbnail(hook: str, channel: dict, output_path: str) -> str:
    """Genera thumbnail YouTube 1280×720 con el hook del vídeo."""
    W, H = 1080, 1920
    primary = _hex_to_rgb(channel["style"].get("primary_color", "#1A1A1A"))
    text_col = _hex_to_rgb(channel["style"].get("text_color", "#FFFFFF"))
    font_path = _find_font()

    img = Image.new("RGB", (W, H), primary)
    draw = ImageDraw.Draw(img)

    # Degradado: oscurece hacia abajo
    dark = tuple(max(0, c - 60) for c in primary)
    for y in range(H):
        t = y / H
        r = int(primary[0] * (1 - t) + dark[0] * t)
        g = int(primary[1] * (1 - t) + dark[1] * t)
        b = int(primary[2] * (1 - t) + dark[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Barra de acento superior
    draw.rectangle([0, 0, W, 14], fill=text_col)

    # Texto principal: hook en mayúsculas, grande y centrado
    clean = _strip_emojis(hook).upper().strip()
    font_size = 110
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # Wrap: máx ~18 chars/línea a este tamaño
    words = clean.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > W - 80 and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)

    lh = font_size + 18
    block_h = len(lines) * lh
    y0 = (H - block_h) // 2 - 20

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tx = (W - (bbox[2] - bbox[0])) // 2
        ty = y0 + i * lh
        # Sombra
        draw.text((tx + 4, ty + 4), line, font=font, fill=(0, 0, 0))
        draw.text((tx, ty), line, font=font, fill=text_col)

    # Nombre del canal abajo
    try:
        small = ImageFont.truetype(font_path, 38) if font_path else ImageFont.load_default()
    except Exception:
        small = ImageFont.load_default()
    ch = channel.get("name", "").upper()
    bbox = draw.textbbox((0, 0), ch, font=small)
    draw.text(((W - (bbox[2] - bbox[0])) // 2, H - 58), ch, font=small,
              fill=tuple(min(255, c + 50) for c in text_col))

    img.save(output_path, "PNG")
    return output_path


def _strip_emojis(text: str) -> str:
    pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
        "\U0001f900-\U0001f9FF\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff"
        "\U00002600-\U000026FF\U0000FE0F]+", flags=re.UNICODE)
    return pattern.sub("", text).strip()


def _wrap_text(text: str, max_chars: int = 16) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if len(test) <= max_chars:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text[:max_chars]]


def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _find_font() -> str:
    candidates = ([
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ] if platform.system() == "Darwin" else [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ])
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""
