"""
Configura los canales de YouTube: descripción, keywords, y genera logos.
Ejecutar una vez: python src/setup_channels.py

Los logos se guardan en assets/logos/ para subir manualmente a YouTube Studio.
La descripción y keywords se actualizan vía API.
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import platform

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CHANNEL_DESCRIPTIONS = {
    "finanzas_clara": {
        "description": (
            "💰 Tips de finanzas personales en español, sin tecnicismos.\n\n"
            "Aprende a ahorrar, invertir y salir de deudas con consejos "
            "prácticos que puedes aplicar hoy mismo.\n\n"
            "📹 Nuevo Short cada día\n"
            "👍 Suscríbete y activa la 🔔\n\n"
            "#finanzaspersonales #ahorro #inversión #dinero"
        ),
        "keywords": "finanzas personales,ahorro,inversión,deudas,presupuesto,dinero,economía,tips financieros",
    },
    "mente_legal": {
        "description": (
            "⚖️ Consejos legales cotidianos explicados simple.\n\n"
            "Tus derechos como consumidor, contratos, reclamaciones y "
            "situaciones legales del día a día en España y Latinoamérica.\n\n"
            "📹 Nuevo Short cada día\n"
            "👍 Suscríbete y activa la 🔔\n\n"
            "#derechos #legal #consumidor #leyes"
        ),
        "keywords": "derecho,legal,consumidor,contratos,reclamaciones,leyes,abogado,derechos laborales",
    },
    "ia_explica": {
        "description": (
            "🤖 Herramientas de IA explicadas para todos.\n\n"
            "Descubre las mejores herramientas de inteligencia artificial, "
            "aprende a usarlas y mantente al día con las novedades tech.\n\n"
            "📹 Nuevo Short cada día\n"
            "👍 Suscríbete y activa la 🔔\n\n"
            "#inteligenciaartificial #IA #tecnología #herramientasIA"
        ),
        "keywords": "inteligencia artificial,IA,AI,herramientas IA,ChatGPT,tecnología,productividad,automatización",
    },
    "salud_longevidad": {
        "description": (
            "🧬 Salud y longevidad basada en ciencia.\n\n"
            "Hábitos saludables, datos científicos y medicina preventiva "
            "explicados de forma accesible. Vive más y mejor.\n\n"
            "📹 Nuevo Short cada día\n"
            "👍 Suscríbete y activa la 🔔\n\n"
            "#salud #longevidad #bienestar #ciencia"
        ),
        "keywords": "salud,longevidad,bienestar,hábitos saludables,ciencia,medicina preventiva,nutrición",
    },
    "mente_prospera": {
        "description": (
            "🚀 Emprendimiento y mentalidad de negocios.\n\n"
            "Casos de éxito, errores comunes y estrategias prácticas "
            "para emprender y hacer crecer tu negocio.\n\n"
            "📹 Nuevo Short cada día\n"
            "👍 Suscríbete y activa la 🔔\n\n"
            "#emprendimiento #negocios #mentalidad #éxito"
        ),
        "keywords": "emprendimiento,negocios,mentalidad,startup,emprender,productividad,éxito,motivación",
    },
}

LOGO_ICONS = {
    "finanzas_clara": "$",
    "mente_legal": "§",
    "ia_explica": "AI",
    "salud_longevidad": "+",
    "mente_prospera": "M",
}


def generate_logos():
    """Genera logos 800x800 para cada canal."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_dir = os.path.join(project_root, "assets", "logos")
    os.makedirs(logo_dir, exist_ok=True)

    channels_dir = os.path.join(project_root, "channels")

    font_path = _find_font()
    try:
        font_big = ImageFont.truetype(font_path, 300)
        font_name = ImageFont.truetype(font_path, 60)
    except Exception:
        font_big = ImageFont.load_default()
        font_name = font_big

    for filename in os.listdir(channels_dir):
        if not filename.endswith(".json"):
            continue
        channel_key = filename.replace(".json", "")
        with open(os.path.join(channels_dir, filename)) as f:
            config = json.load(f)

        name = config["name"]
        color_hex = config["style"]["primary_color"]
        color_rgb = tuple(int(color_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        icon = LOGO_ICONS.get(channel_key, name[0])

        # Crear imagen 800x800
        img = Image.new("RGB", (800, 800), color_rgb)
        draw = ImageDraw.Draw(img)

        # Icono grande centrado
        bbox = draw.textbbox((0, 0), icon, font=font_big)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(((800 - tw) / 2, (800 - th) / 2 - 60), icon, font=font_big, fill=(255, 255, 255))

        # Nombre del canal abajo
        bbox2 = draw.textbbox((0, 0), name, font=font_name)
        tw2 = bbox2[2] - bbox2[0]
        draw.text(((800 - tw2) / 2, 680), name, font=font_name, fill=(255, 255, 255, 200))

        path = os.path.join(logo_dir, f"{channel_key}.png")
        img.save(path, "PNG")
        log.info("Logo generado: %s", path)


def update_channel_descriptions():
    """Actualiza descripción y keywords de cada canal vía YouTube API."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    channels_dir = os.path.join(project_root, "channels")

    for filename in os.listdir(channels_dir):
        if not filename.endswith(".json"):
            continue
        channel_key = filename.replace(".json", "")
        with open(os.path.join(channels_dir, filename)) as f:
            config = json.load(f)

        info = CHANNEL_DESCRIPTIONS.get(channel_key)
        if not info:
            continue

        token_env = config.get("refresh_token_env", "YOUTUBE_REFRESH_TOKEN")
        refresh_token = os.getenv(token_env)
        if not refresh_token:
            log.warning("No token para %s (%s)", channel_key, token_env)
            continue

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("YOUTUBE_CLIENT_ID"),
            client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/youtube"],
        )

        youtube = build("youtube", "v3", credentials=creds)

        # Obtener canal actual
        resp = youtube.channels().list(part="brandingSettings", mine=True).execute()
        if not resp.get("items"):
            log.warning("No se encontró canal para %s", channel_key)
            continue

        channel = resp["items"][0]
        channel_id = channel["id"]

        # Actualizar branding
        channel["brandingSettings"]["channel"]["description"] = info["description"]
        channel["brandingSettings"]["channel"]["keywords"] = info["keywords"]
        channel["brandingSettings"]["channel"]["defaultLanguage"] = "es"

        youtube.channels().update(
            part="brandingSettings",
            body=channel,
        ).execute()

        log.info("Descripción actualizada: %s (%s)", config["name"], channel_id)


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


if __name__ == "__main__":
    print("=== Generando logos ===")
    generate_logos()
    print("\n=== Actualizando descripciones ===")
    update_channel_descriptions()
    print("\n¡Listo! Sube los logos manualmente desde assets/logos/ a YouTube Studio.")
