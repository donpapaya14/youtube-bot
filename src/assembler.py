"""
Ensamblaje de video final con FFmpeg + Pillow.
- Concatena clips de video como fondo
- Genera texto como imágenes PNG transparentes (Pillow)
- Overlay directo de PNGs sobre fondo con enable=between() (sin drawtext)
- Música de fondo opcional
- Formato vertical 9:16 (1080x1920), máximo 60 segundos
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
    """Ensambla video final. Devuelve path al archivo generado."""
    work_dir = tempfile.mkdtemp(prefix="ytbot_")

    # 1. Procesar clips a formato vertical
    processed = _process_clips(clips, work_dir)
    if not processed:
        raise RuntimeError("No hay clips procesados para ensamblar")

    # 2. Concatenar clips de fondo
    concat_path = os.path.join(work_dir, "concat.mp4")
    _concat_clips(processed, concat_path)

    # 3. Duración total de slides
    total_duration = sum(s["duration"] for s in text_slides)
    total_duration = min(total_duration, 59)

    # 4. Generar imágenes PNG para cada slide
    slide_pngs = _generate_slide_pngs(text_slides, style, work_dir)

    # 5. Componer: fondo (looped) + overlay PNGs + audio
    _compose_final(concat_path, slide_pngs, text_slides, total_duration, output_path, music_path)

    size_kb = os.path.getsize(output_path) / 1024
    log.info("Video ensamblado: %s (%.0f KB)", output_path, size_kb)
    return output_path


def _process_clips(clips: list[str], work_dir: str) -> list[str]:
    """Redimensiona cada clip a 1080x1920, quita audio."""
    processed = []
    for i, clip in enumerate(clips):
        out = os.path.join(work_dir, f"proc_{i}.mp4")
        # Anti-fingerprint: variaciones aleatorias imperceptibles
        bright = round(random.uniform(-0.03, 0.03), 3)
        sat = round(random.uniform(0.97, 1.03), 3)
        crop_x = random.randint(0, 6)
        crop_y = random.randint(0, 6)
        scale_w = WIDTH + crop_x * 2
        scale_h = HEIGHT + crop_y * 2
        cmd = [
            "ffmpeg", "-y", "-i", clip,
            "-vf", (
                f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT}:{crop_x}:{crop_y},setsar=1,"
                f"eq=brightness={bright}:saturation={sat}"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", str(random.randint(17, 19)),
            "-an", "-r", "30", "-t", "20",
            out,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            processed.append(out)
        else:
            log.warning("Error procesando clip %d: %s", i, result.stderr[-200:])
    return processed


def _concat_clips(clips: list[str], output: str):
    """Concatena clips."""
    list_file = output + ".txt"
    with open(list_file, "w") as f:
        for clip in clips:
            f.write(f"file '{clip}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-r", "30",
        output,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Error concatenando: {result.stderr[-300:]}")


def _generate_slide_pngs(slides: list[dict], style: dict, work_dir: str) -> list[str]:
    """Genera PNG transparente por cada slide de texto."""
    font_path = _find_font()
    font_size = style.get("font_size", 56)
    primary_color = style.get("primary_color", "#1A1A1A")
    text_color = style.get("text_color", "#FFFFFF")
    box_opacity = int(style.get("box_opacity", 0.85) * 255)

    bg_rgb = _hex_to_rgb(primary_color)
    txt_rgb = _hex_to_rgb(text_color)

    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    paths = []
    for i, slide in enumerate(slides):
        png_path = os.path.join(work_dir, f"slide_{i}.png")
        _render_slide(slide["text"], font, font_size, bg_rgb, box_opacity, txt_rgb, png_path)
        paths.append(png_path)

    return paths


def _render_slide(text: str, font, font_size: int, bg_rgb: tuple, bg_opacity: int, txt_rgb: tuple, output: str):
    """Renderiza un slide de texto como PNG con fondo transparente."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_chars = max(14, int(WIDTH / (font_size * 0.52)))
    lines = _wrap_text(text, max_chars)

    line_h = font_size + 20
    block_h = len(lines) * line_h + 48

    widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        widths.append(bbox[2] - bbox[0])
    block_w = max(widths) + 72 if widths else WIDTH // 2

    box_x = (WIDTH - block_w) / 2
    box_y = (HEIGHT - block_h) / 2

    # Fondo semitransparente con esquinas redondeadas
    draw.rounded_rectangle(
        [box_x, box_y, box_x + block_w, box_y + block_h],
        radius=24,
        fill=bg_rgb + (bg_opacity,),
    )

    # Texto centrado con sombra
    for j, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        tx = (WIDTH - tw) / 2
        ty = box_y + 24 + j * line_h

        draw.text((tx + 3, ty + 3), line, font=font, fill=(0, 0, 0, 160))
        draw.text((tx, ty), line, font=font, fill=txt_rgb + (255,))

    img.save(output, "PNG")


def _compose_final(
    bg_video: str, slide_pngs: list[str], slides: list[dict],
    total_duration: float, output: str, music_path: str | None,
):
    """Compone video final: fondo en loop + overlay de PNGs por tiempo + audio."""
    # Construir inputs: -stream_loop para fondo + cada PNG
    inputs = ["-stream_loop", "-1", "-i", bg_video]
    for png in slide_pngs:
        inputs += ["-i", png]

    # Construir filter_complex: overlay secuencial con enable=between
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

    # Añadir audio (música o silencio)
    if music_path and os.path.exists(music_path):
        audio_input_idx = len(slide_pngs) + 1
        inputs += ["-i", music_path]
        filter_str += f";[{audio_input_idx}:a]volume=0.18,afade=t=out:st={total_duration-3}:d=3[aout]"
        audio_map = ["-map", "[aout]"]
    else:
        filter_str += f";anullsrc=r=44100:cl=stereo[aout]"
        audio_map = ["-map", "[aout]"]

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", last_label,
        *audio_map,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "128k",
        "-r", "30",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        output,
    ]

    log.info("FFmpeg compose: %d slides, %.0fs duración", len(slides), total_duration)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        log.error("FFmpeg stderr: %s", result.stderr[-800:])
        raise RuntimeError(f"Error en composición final: {result.stderr[-500:]}")


def _wrap_text(text: str, max_chars: int = 22) -> list[str]:
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
            "/System/Library/Fonts/SFNS.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""
