"""
Ensamblaje de video VIRAL para YouTube Shorts.
Optimizado para retención: ritmo rápido, zoom effects, transiciones dinámicas.
"""

import logging
import os
import platform
import random
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

WIDTH = 1080
HEIGHT = 1920


def assemble_video(
    clips: list[str],
    text_slides: list[dict],
    style: dict,
    output_path: str,
    music_path: str | None = None,
) -> str:
    work_dir = tempfile.mkdtemp(prefix="ytbot_")

    processed = _process_clips(clips, work_dir)
    if not processed:
        raise RuntimeError("No hay clips procesados")

    concat_path = os.path.join(work_dir, "concat.mp4")
    _concat_clips(processed, concat_path)

    total_duration = sum(s["duration"] for s in text_slides)
    # Sweet spot viral: 25-35s. Si slides suman menos, estirar proporcional
    if total_duration < 25:
        factor = 25 / total_duration
        for s in text_slides:
            s["duration"] = round(s["duration"] * factor, 1)
        total_duration = sum(s["duration"] for s in text_slides)
    total_duration = min(total_duration, 35)

    slide_pngs = _generate_slide_pngs(text_slides, style, work_dir)
    _compose_final(concat_path, slide_pngs, text_slides, total_duration, output_path, music_path)

    size_kb = os.path.getsize(output_path) / 1024
    log.info("Video ensamblado: %s (%.0f KB)", output_path, size_kb)
    return output_path


def _process_clips(clips: list[str], work_dir: str) -> list[str]:
    """Procesa clips con zoom lento (Ken Burns effect) para dinamismo."""
    processed = []
    for i, clip in enumerate(clips):
        out = os.path.join(work_dir, f"proc_{i}.mp4")

        # Anti-fingerprint + Ken Burns zoom effect
        bright = round(random.uniform(-0.02, 0.02), 3)
        sat = round(random.uniform(0.98, 1.04), 3)

        # Zoom lento: empezar al 100% y zoom in a 110% (o viceversa)
        if random.random() > 0.5:
            # Zoom in
            zoom_filter = (
                f"scale=1200:2132,zoompan=z='min(zoom+0.002,1.1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d=300:s={WIDTH}x{HEIGHT}:fps=30"
            )
        else:
            # Pan horizontal lento
            zoom_filter = (
                f"scale=1300:2310:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT}:x='(iw-{WIDTH})*t/10':y='(ih-{HEIGHT})/2',"
                f"setsar=1"
            )

        cmd = [
            "ffmpeg", "-y", "-i", clip,
            "-vf", f"{zoom_filter},eq=brightness={bright}:saturation={sat}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(random.randint(19, 22)),
            "-an", "-r", "30", "-t", "10",
            out,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            processed.append(out)
        else:
            # Fallback sin zoom si falla
            cmd_simple = [
                "ffmpeg", "-y", "-i", clip,
                "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                "-an", "-r", "30", "-t", "10",
                out,
            ]
            result2 = subprocess.run(cmd_simple, capture_output=True, text=True, timeout=300)
            if result2.returncode == 0:
                processed.append(out)
            else:
                log.warning("Error clip %d: %s", i, result2.stderr[-200:])
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
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Error concatenando: {result.stderr[-300:]}")


def _generate_slide_pngs(slides: list[dict], style: dict, work_dir: str) -> list[str]:
    font_path = _find_font()
    font_size = style.get("font_size", 58)
    primary_color = style.get("primary_color", "#1A1A1A")
    text_color = style.get("text_color", "#FFFFFF")
    box_opacity = int(style.get("box_opacity", 0.85) * 255)

    bg_rgb = _hex_to_rgb(primary_color)
    txt_rgb = _hex_to_rgb(text_color)

    try:
        font = ImageFont.truetype(font_path, font_size)
        font_bold = ImageFont.truetype(font_path, font_size + 4)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font

    paths = []
    for i, slide in enumerate(slides):
        png_path = os.path.join(work_dir, f"slide_{i}.png")
        _render_slide(slide["text"], font, font_bold, font_size, bg_rgb, box_opacity, txt_rgb, png_path, i, len(slides))
        paths.append(png_path)
    return paths


def _render_slide(
    text: str, font, font_bold, font_size: int,
    bg_rgb: tuple, bg_opacity: int, txt_rgb: tuple,
    output: str, slide_idx: int, total_slides: int,
):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Limpiar emojis del texto (no renderizan bien en Linux)
    text = _strip_emojis(text)

    # Max 16 chars por línea → texto NUNCA se sale de la pantalla
    max_chars = 16
    lines = _wrap_text(text, max_chars)

    line_h = font_size + 24
    block_h = len(lines) * line_h + 56

    # Calcular ancho real del texto renderizado
    widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_bold)
        widths.append(bbox[2] - bbox[0])
    block_w = max(widths) + 100 if widths else WIDTH // 2
    # NUNCA exceder el 85% del ancho de pantalla
    block_w = min(block_w, int(WIDTH * 0.85))

    box_x = (WIDTH - block_w) / 2
    box_y = HEIGHT * 0.40

    # Fondo con bordes redondeados
    draw.rounded_rectangle(
        [box_x, box_y, box_x + block_w, box_y + block_h],
        radius=28,
        fill=bg_rgb + (bg_opacity,),
    )

    # Barra de progreso arriba (sutil)
    progress = (slide_idx + 1) / total_slides
    bar_w = int((WIDTH - 120) * progress)
    draw.rounded_rectangle(
        [60, 120, 60 + bar_w, 128],
        radius=4,
        fill=txt_rgb + (100,),
    )
    # Fondo barra
    draw.rounded_rectangle(
        [60, 120, WIDTH - 60, 128],
        radius=4,
        fill=(255, 255, 255, 30),
    )

    # Texto centrado con sombra fuerte
    for j, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_bold)
        tw = bbox[2] - bbox[0]
        tx = (WIDTH - tw) / 2
        ty = box_y + 26 + j * line_h

        # Sombra fuerte
        draw.text((tx + 3, ty + 3), line, font=font_bold, fill=(0, 0, 0, 200))
        draw.text((tx + 1, ty + 1), line, font=font_bold, fill=(0, 0, 0, 120))
        # Texto principal
        draw.text((tx, ty), line, font=font_bold, fill=txt_rgb + (255,))

    img.save(output, "PNG")


def _compose_final(
    bg_video: str, slide_pngs: list[str], slides: list[dict],
    total_duration: float, output: str, music_path: str | None,
):
    inputs = ["-stream_loop", "-1", "-i", bg_video]
    for png in slide_pngs:
        inputs += ["-i", png]

    filters = []
    current_time = 0.0

    for i, slide in enumerate(slides):
        duration = slide["duration"]
        start = current_time
        end = current_time + duration

        src = f"[v{i}]" if i > 0 else "[0:v]"
        dst = f"[v{i+1}]"
        img_input = f"[{i+1}:v]"

        filters.append(
            f"{src}{img_input}overlay=0:0:enable='between(t,{start:.1f},{end:.1f})'{dst}"
        )
        current_time = end

    last_label = f"[v{len(slides)}]"
    filter_str = ";".join(filters)

    if music_path and os.path.exists(music_path):
        audio_input_idx = len(slide_pngs) + 1
        inputs += ["-i", music_path]
        # Música más alta para Shorts (vol 0.3) + fade out
        filter_str += f";[{audio_input_idx}:a]volume=0.30,afade=t=out:st={total_duration-2}:d=2[aout]"
        audio_map = ["-map", "[aout]"]
    else:
        filter_str += ";anullsrc=r=44100:cl=stereo[aout]"
        audio_map = ["-map", "[aout]"]

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", last_label,
        *audio_map,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-r", "30",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        output,
    ]

    log.info("FFmpeg compose: %d slides, %.0fs duración", len(slides), total_duration)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        log.error("FFmpeg stderr: %s", result.stderr[-800:])
        raise RuntimeError(f"Error composición: {result.stderr[-500:]}")


def _strip_emojis(text: str) -> str:
    """Elimina emojis del texto para evitar caracteres rotos en video."""
    import re
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
        "\U0001f900-\U0001f9FF\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff"
        "\U00002600-\U000026FF\U0000FE0F]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()


def _wrap_text(text: str, max_chars: int = 16) -> list[str]:
    words = text.split()
    lines = []
    current = ""
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
    return lines if lines else [text[:max_chars]]


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _find_font() -> str:
    if platform.system() == "Darwin":
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""
