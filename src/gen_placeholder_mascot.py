"""
Genera mascotas PLACEHOLDER (4 poses) para validar el pipeline de overlay.
Sustituir por la caricatura real (PNGs transparentes) cuando esté lista.

Uso: python src/gen_placeholder_mascot.py [canal_dir]
     por defecto -> assets/mascots/vidasana360
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 600, 900
SKIN = (245, 213, 180, 255)
BODY = (198, 40, 40, 255)        # rojo VidaSana360
DARK = (40, 40, 40, 255)
WHITE = (255, 255, 255, 255)
POSES = ["wave", "point", "thumb", "think"]


def _font(size):
    for p in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _draw_arm(d, pose):
    """Brazo derecho según la pose."""
    if pose == "wave":
        d.line([(390, 470), (470, 300)], fill=SKIN, width=46)
        d.ellipse([445, 270, 505, 330], fill=SKIN)
    elif pose == "point":
        d.line([(390, 470), (520, 430)], fill=SKIN, width=46)
        d.ellipse([500, 405, 560, 465], fill=SKIN)
    elif pose == "thumb":
        d.line([(390, 470), (480, 430)], fill=SKIN, width=46)
        d.ellipse([460, 400, 520, 470], fill=SKIN)
        d.line([(490, 430), (490, 380)], fill=SKIN, width=22)  # pulgar arriba
    else:  # think
        d.line([(390, 470), (330, 330)], fill=SKIN, width=46)
        d.ellipse([300, 300, 360, 360], fill=SKIN)


def make_pose(pose: str, out_path: str):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Cuerpo
    d.rounded_rectangle([180, 360, 420, 820], radius=70, fill=BODY)
    # Brazo izquierdo (reposo)
    d.line([(210, 470), (150, 620)], fill=SKIN, width=46)
    d.ellipse([125, 600, 185, 660], fill=SKIN)
    # Brazo derecho (según pose)
    _draw_arm(d, pose)
    # Cuello
    d.rectangle([270, 320, 330, 380], fill=SKIN)
    # Cabeza
    d.ellipse([180, 130, 420, 370], fill=SKIN)
    # Pelo
    d.pieslice([180, 110, 420, 320], 180, 360, fill=DARK)
    # Ojos
    eye_y = 250
    d.ellipse([245, eye_y, 275, eye_y + 30], fill=DARK)
    d.ellipse([325, eye_y, 355, eye_y + 30], fill=DARK)
    # Sonrisa
    d.arc([260, 270, 340, 330], 20, 160, fill=DARK, width=8)

    # Etiqueta PLACEHOLDER + pose
    f = _font(34)
    fs = _font(26)
    label = "PLACEHOLDER"
    bw = d.textbbox((0, 0), label, font=f)[2]
    d.rectangle([(W - bw) // 2 - 16, 835, (W + bw) // 2 + 16, 895], fill=(0, 0, 0, 180))
    d.text(((W - bw) // 2, 842), label, font=f, fill=WHITE)
    pw = d.textbbox((0, 0), pose, font=fs)[2]
    d.text(((W - pw) // 2, 838 + 0), pose, font=fs, fill=(255, 220, 0, 255))

    img.save(out_path, "PNG")
    return out_path


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets", "mascots", "vidasana360")
    os.makedirs(out_dir, exist_ok=True)
    for pose in POSES:
        p = make_pose(pose, os.path.join(out_dir, f"pose_{pose}.png"))
        print(f"  generado {p}")
    print(f"OK: 4 placeholders en {out_dir}")


if __name__ == "__main__":
    main()
