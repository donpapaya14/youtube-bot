"""
Genera logos (800x800) y banners (2560x1440) profesionales para 6 canales.
Diseño limpio, moderno, con identidad de marca.
"""

import math
import os
import platform
from PIL import Image, ImageDraw, ImageFont

LOGO_SIZE = (800, 800)
BANNER_SIZE = (2560, 1440)

# Configuración de marca por canal
CHANNELS = {
    "finanzas_clara": {
        "name": "FinanzasClara",
        "tagline": "Tu dinero, tus reglas",
        "icon": "💰",
        "colors": {
            "primary": "#1B5E20",      # Verde oscuro
            "secondary": "#4CAF50",    # Verde medio
            "accent": "#A5D6A7",       # Verde claro
            "gradient_end": "#0D3B0F", # Verde muy oscuro
            "text": "#FFFFFF",
        },
    },
    "mente_legal": {
        "name": "MenteLegal",
        "tagline": "Tus derechos, explicados simple",
        "icon": "⚖️",
        "colors": {
            "primary": "#1A237E",
            "secondary": "#3F51B5",
            "accent": "#9FA8DA",
            "gradient_end": "#0D1042",
            "text": "#FFFFFF",
        },
    },
    "ia_explica": {
        "name": "IAExplica",
        "tagline": "La IA al alcance de todos",
        "icon": "🤖",
        "colors": {
            "primary": "#6A1B9A",
            "secondary": "#AB47BC",
            "accent": "#CE93D8",
            "gradient_end": "#38006B",
            "text": "#FFFFFF",
        },
    },
    "salud_longevidad": {
        "name": "SaludLongevidad",
        "tagline": "Vive más, vive mejor",
        "icon": "🧬",
        "colors": {
            "primary": "#00695C",
            "secondary": "#00897B",
            "accent": "#80CBC4",
            "gradient_end": "#003D33",
            "text": "#FFFFFF",
        },
    },
    "mente_prospera": {
        "name": "MentePróspera",
        "tagline": "Emprende con mentalidad ganadora",
        "icon": "🚀",
        "colors": {
            "primary": "#E65100",
            "secondary": "#FB8C00",
            "accent": "#FFB74D",
            "gradient_end": "#8C3000",
            "text": "#FFFFFF",
        },
    },
    "canal_principal": {
        "name": "VidaSana360",
        "tagline": "Ciencia y bienestar para transformar tu vida",
        "icon": "💪",
        "colors": {
            "primary": "#C62828",
            "secondary": "#EF5350",
            "accent": "#EF9A9A",
            "gradient_end": "#7B1A1A",
            "text": "#FFFFFF",
        },
    },
}


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def interpolate_color(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def draw_gradient(draw, bbox, color1, color2, direction="vertical"):
    x0, y0, x1, y1 = bbox
    if direction == "vertical":
        for y in range(y0, y1):
            t = (y - y0) / max(1, (y1 - y0))
            c = interpolate_color(color1, color2, t)
            draw.line([(x0, y), (x1, y)], fill=c)
    else:
        for x in range(x0, x1):
            t = (x - x0) / max(1, (x1 - x0))
            c = interpolate_color(color1, color2, t)
            draw.line([(x, y0), (x, y1)], fill=c)


def draw_circles(draw, width, height, color, count=15, min_r=20, max_r=120):
    """Dibuja círculos decorativos semitransparentes."""
    import random
    random.seed(42)  # Reproducible
    for _ in range(count):
        r = random.randint(min_r, max_r)
        x = random.randint(-r, width + r)
        y = random.randint(-r, height + r)
        opacity = random.randint(15, 40)
        c = hex_to_rgb(color) + (opacity,)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=c)


def draw_geometric_pattern(draw, width, height, color, element="lines"):
    """Añade patrón geométrico sutil."""
    import random
    random.seed(123)
    c = hex_to_rgb(color)

    if element == "lines":
        for i in range(0, max(width, height) * 2, 80):
            opacity = 20
            line_color = c + (opacity,)
            draw.line([(i, 0), (0, i)], fill=line_color, width=1)
    elif element == "dots":
        for x in range(40, width, 60):
            for y in range(40, height, 60):
                opacity = 15 + (x * y) % 20
                draw.ellipse([x-2, y-2, x+2, y+2], fill=c + (opacity,))


def create_logo(channel_key, config, output_dir, fonts):
    """Crea logo 800x800 profesional."""
    w, h = LOGO_SIZE
    colors = config["colors"]
    primary = hex_to_rgb(colors["primary"])
    secondary = hex_to_rgb(colors["secondary"])
    accent = hex_to_rgb(colors["accent"])
    gradient_end = hex_to_rgb(colors["gradient_end"])

    # Imagen base RGBA
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # Capa de fondo con gradiente
    bg = Image.new("RGBA", (w, h))
    bg_draw = ImageDraw.Draw(bg)
    draw_gradient(bg_draw, (0, 0, w, h), primary, gradient_end)
    img = Image.alpha_composite(img, bg)

    # Capa de decoración
    deco = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    deco_draw = ImageDraw.Draw(deco)
    draw_circles(deco_draw, w, h, colors["accent"], count=12, min_r=40, max_r=180)
    img = Image.alpha_composite(img, deco)

    # Marco circular central
    center = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    center_draw = ImageDraw.Draw(center)

    # Círculo exterior (accent con transparencia)
    cx, cy = w // 2, h // 2 - 40
    r_outer = 260
    r_inner = 230
    center_draw.ellipse(
        [cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
        fill=accent + (60,),
    )
    # Círculo interior (oscuro)
    center_draw.ellipse(
        [cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner],
        fill=gradient_end + (200,),
    )
    img = Image.alpha_composite(img, center)

    # Icono emoji grande centrado
    final_draw = ImageDraw.Draw(img)
    icon = config["icon"]
    try:
        # Intentar renderizar emoji con fuente del sistema
        emoji_font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 160)
        bbox = final_draw.textbbox((0, 0), icon, font=emoji_font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        final_draw.text((cx - tw // 2, cy - th // 2 - 10), icon, font=emoji_font)
    except Exception:
        # Fallback: letra grande
        letter = config["name"][0]
        bbox = final_draw.textbbox((0, 0), letter, font=fonts["huge"])
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        final_draw.text((cx - tw // 2, cy - th // 2), letter, font=fonts["huge"], fill=(255, 255, 255))

    # Nombre del canal abajo
    name = config["name"]
    # Línea separadora
    line_y = h - 195
    line_w = 200
    final_draw.line(
        [(cx - line_w, line_y), (cx + line_w, line_y)],
        fill=accent + (150,), width=2,
    )

    bbox = final_draw.textbbox((0, 0), name, font=fonts["name"])
    tw = bbox[2] - bbox[0]
    final_draw.text(
        ((w - tw) // 2, h - 175),
        name, font=fonts["name"], fill=(255, 255, 255),
    )

    # Tagline pequeño
    tagline = config["tagline"]
    bbox2 = final_draw.textbbox((0, 0), tagline, font=fonts["small"])
    tw2 = bbox2[2] - bbox2[0]
    final_draw.text(
        ((w - tw2) // 2, h - 110),
        tagline, font=fonts["small"], fill=accent + (200,),
    )

    # Guardar
    path = os.path.join(output_dir, f"{channel_key}_logo.png")
    img.convert("RGB").save(path, "PNG", quality=95)
    print(f"  ✓ Logo: {path}")
    return path


def create_banner(channel_key, config, output_dir, fonts):
    """Crea banner 2560x1440 profesional."""
    w, h = BANNER_SIZE
    colors = config["colors"]
    primary = hex_to_rgb(colors["primary"])
    secondary = hex_to_rgb(colors["secondary"])
    accent = hex_to_rgb(colors["accent"])
    gradient_end = hex_to_rgb(colors["gradient_end"])

    img = Image.new("RGBA", (w, h))

    # Gradiente diagonal
    bg = Image.new("RGBA", (w, h))
    bg_draw = ImageDraw.Draw(bg)

    for y in range(h):
        for x_step in range(0, w, 4):
            t = (x_step / w * 0.6 + y / h * 0.4)
            t = min(1.0, max(0.0, t))
            c = interpolate_color(primary, gradient_end, t)
            bg_draw.line([(x_step, y), (x_step + 4, y)], fill=c)

    img = Image.alpha_composite(img, bg)

    # Patrón geométrico sutil
    pattern = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pattern_draw = ImageDraw.Draw(pattern)
    draw_geometric_pattern(pattern_draw, w, h, colors["accent"], "lines")
    draw_circles(pattern_draw, w, h, colors["secondary"], count=20, min_r=50, max_r=250)
    img = Image.alpha_composite(img, pattern)

    # Barra central (zona segura TV: 1546x423 centrada en 2560x1440)
    # Zona segura móvil: 1546x423 centrada
    final_draw = ImageDraw.Draw(img)

    # Franja horizontal sutil
    bar_y = h // 2 - 100
    bar_h = 200
    bar = Image.new("RGBA", (w, bar_h), gradient_end + (80,))
    img.paste(bar, (0, bar_y), bar)
    final_draw = ImageDraw.Draw(img)

    # Nombre del canal centrado
    name = config["name"]
    bbox = final_draw.textbbox((0, 0), name, font=fonts["banner_title"])
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    name_x = (w - tw) // 2
    name_y = h // 2 - th // 2 - 30

    # Sombra
    final_draw.text((name_x + 3, name_y + 3), name, font=fonts["banner_title"], fill=(0, 0, 0, 100))
    final_draw.text((name_x, name_y), name, font=fonts["banner_title"], fill=(255, 255, 255))

    # Tagline debajo
    tagline = config["tagline"]
    bbox2 = final_draw.textbbox((0, 0), tagline, font=fonts["banner_sub"])
    tw2 = bbox2[2] - bbox2[0]
    tag_x = (w - tw2) // 2
    tag_y = name_y + th + 15
    final_draw.text((tag_x, tag_y), tagline, font=fonts["banner_sub"], fill=accent)

    # Líneas decorativas a los lados del nombre
    line_y_center = name_y + th // 2
    margin = 50
    line_len = 200
    # Izquierda
    final_draw.line(
        [(name_x - margin - line_len, line_y_center), (name_x - margin, line_y_center)],
        fill=accent + (120,), width=2,
    )
    # Derecha
    final_draw.line(
        [(name_x + tw + margin, line_y_center), (name_x + tw + margin + line_len, line_y_center)],
        fill=accent + (120,), width=2,
    )

    # Icono a la izquierda del nombre
    try:
        emoji_font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 80)
        icon = config["icon"]
        final_draw.text((name_x - 120, name_y + 5), icon, font=emoji_font)
    except Exception:
        pass

    # "Suscríbete" pequeño abajo
    sub_text = "📹 Nuevo contenido cada día · Suscríbete"
    bbox3 = final_draw.textbbox((0, 0), sub_text, font=fonts["small"])
    tw3 = bbox3[2] - bbox3[0]
    final_draw.text(
        ((w - tw3) // 2, h // 2 + 100),
        sub_text, font=fonts["small"], fill=(255, 255, 255, 180),
    )

    path = os.path.join(output_dir, f"{channel_key}_banner.png")
    img.convert("RGB").save(path, "PNG", quality=95)
    print(f"  ✓ Banner: {path}")
    return path


def load_fonts():
    """Carga fuentes del sistema."""
    if platform.system() == "Darwin":
        bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        regular = "/System/Library/Fonts/Supplemental/Arial.ttf"
        rounded = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
        futura = "/System/Library/Fonts/Supplemental/Futura.ttc"
    else:
        bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        rounded = bold
        futura = bold

    # Usar Futura si disponible (más moderna), fallback a Arial
    title_font = futura if os.path.exists(futura) else bold

    return {
        "huge": ImageFont.truetype(bold, 240),
        "name": ImageFont.truetype(title_font, 62),
        "small": ImageFont.truetype(regular, 32),
        "banner_title": ImageFont.truetype(title_font, 120),
        "banner_sub": ImageFont.truetype(regular, 48),
    }


def main():
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "logos",
    )
    os.makedirs(output_dir, exist_ok=True)

    print("Cargando fuentes...")
    fonts = load_fonts()

    for key, config in CHANNELS.items():
        print(f"\n🎨 {config['name']}:")
        create_logo(key, config, output_dir, fonts)
        create_banner(key, config, output_dir, fonts)

    print(f"\n✅ Todo en: {output_dir}")
    print("\nSube manualmente a YouTube Studio:")
    print("  Logo → Personalización → Branding → Imagen de perfil")
    print("  Banner → Personalización → Branding → Imagen de banner")


if __name__ == "__main__":
    main()
