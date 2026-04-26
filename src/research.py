"""
Investigación de tendencias y generación de contenido con VALOR REAL.
Cada Short debe enseñar algo CONCRETO y ÚTIL que el espectador pueda aplicar.
"""

import json
import logging
import os
from groq import Groq
from openai import OpenAI

log = logging.getLogger(__name__)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
github_client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.getenv("GITHUB_TOKEN"),
)

GROQ_MODEL = "llama-3.3-70b-versatile"
GITHUB_MODEL = "DeepSeek-V3-0324"


def _call_groq(prompt: str, temperature: float = 0.9) -> dict:
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return json.loads(response.choices[0].message.content)


def _call_github(prompt: str, temperature: float = 0.8) -> dict:
    response = github_client.chat.completions.create(
        model=GITHUB_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def _call_with_fallback(prompt: str, primary: str = "groq", temperature: float = 0.9) -> dict:
    funcs = {"groq": _call_groq, "github": _call_github}
    fallback = "github" if primary == "groq" else "groq"
    try:
        return funcs[primary](prompt, temperature)
    except Exception as e:
        log.warning("%s falló: %s. Intentando %s...", primary, e, fallback)
        return funcs[fallback](prompt, temperature)


# Tipos de contenido con valor real, por nicho
CONTENT_FORMULAS = {
    "finanzas": [
        "Tutorial: método concreto para ahorrar X€/mes (con números reales y pasos exactos)",
        "Lista: 3 apps GRATUITAS con nombre real para gestionar dinero (nombre + qué hace cada una)",
        "Hack: truco bancario específico que poca gente conoce (con ejemplo numérico)",
        "Error: error financiero concreto con ejemplo de cuánto dinero pierdes",
        "Comparativa: producto financiero A vs B con números reales",
    ],
    "legal": [
        "Derecho: un derecho específico que tienes y no sabías (con artículo de ley)",
        "Situación: qué hacer paso a paso si te pasa X (con acciones concretas)",
        "Truco legal: cómo reclamar X con plantilla/modelo exacto",
        "Error: error legal común y consecuencias reales con ejemplo",
        "Plazo: plazos legales concretos que debes conocer (días exactos)",
    ],
    "ia": [
        "Tutorial: herramienta de IA GRATUITA concreta con nombre real — qué hace y cómo usarla paso a paso",
        "Hack: prompt exacto para ChatGPT/Gemini que resuelve un problema específico (escribir el prompt literal)",
        "Lista: 3 herramientas IA gratuitas con NOMBRE REAL que reemplazan software de pago (nombrar cuáles)",
        "Novedad: función nueva de una herramienta IA específica lanzada recientemente",
        "Comparativa: herramienta A vs herramienta B para tarea específica (con nombres reales)",
    ],
    "salud": [
        "Estudio: hallazgo científico concreto de universidad real (nombrar universidad y año)",
        "Hábito: hábito específico con beneficio medible (ej: caminar 20 min reduce presión arterial 10%)",
        "Alimento: alimento concreto con beneficio respaldado por ciencia (nombrar estudio)",
        "Mito: mito de salud común desmontado con datos reales",
        "Rutina: rutina de 5 minutos con pasos exactos para mejorar X",
    ],
    "negocio": [
        "Caso real: persona real que logró X con método Y (nombre o ejemplo verificable)",
        "Estrategia: táctica de ventas/marketing concreta con pasos numerados",
        "Error: error de emprendedor con consecuencia real y cómo evitarlo",
        "Herramienta: herramienta gratuita con nombre real para emprendedores",
        "Número: dato económico concreto sobre un sector con fuente",
    ],
}

NICHE_MAP = {
    "finanzas_clara": "finanzas",
    "mente_legal": "legal",
    "ia_explica": "ia",
    "salud_longevidad": "salud",
    "mente_prospera": "negocio",
}


def research_topic(channel: dict) -> dict:
    """Genera tema con VALOR REAL y contenido específico."""
    import random

    channel_key = channel.get("handle", "").replace("@", "").split("-")[0].lower()
    # Detectar nicho desde config
    niche_key = None
    for key, niche in NICHE_MAP.items():
        if key in channel.get("name", "").lower() or key in str(channel.get("niche", "")).lower():
            niche_key = niche
            break
    if not niche_key:
        niche_key = "ia"

    formulas = CONTENT_FORMULAS.get(niche_key, CONTENT_FORMULAS["ia"])
    formula = random.choice(formulas)

    prompt = f"""Eres un creador de YouTube Shorts educativos en español con MILLONES de vistas.
Canal: {channel['name']}
Nicho: {channel['niche']}
Tono: {channel['tone']}

TIPO DE VIDEO A CREAR: {formula}

REGLAS CRÍTICAS:
- Todo dato debe ser REAL y VERIFICABLE
- Nombrar herramientas, leyes, estudios, personas REALES
- Dar INFORMACIÓN CONCRETA que el espectador pueda USAR HOY
- CERO frases genéricas tipo "la IA es muy potente" o "el dinero es importante"
- Cada punto debe enseñar algo ESPECÍFICO y NUEVO

Responde SOLO con JSON válido:
{{
  "topic": "tema específico y concreto",
  "hook": "pregunta o dato CONCRETO que pare el scroll (máx 10 palabras)",
  "key_points": [
    "dato específico 1 con nombre/número real",
    "dato específico 2",
    "dato específico 3",
    "dato específico 4",
    "conclusión accionable"
  ],
  "search_terms": ["búsqueda video en inglés 1", "término 2", "término 3"]
}}"""

    data = _call_with_fallback(prompt, primary="groq", temperature=0.9)
    log.info("Tema elegido: %s", data["topic"])
    return data


def generate_content(channel: dict, topic_data: dict) -> dict:
    """Genera slides con CONTENIDO REAL, no relleno."""
    prompt = f"""Genera contenido para un YouTube Short educativo VIRAL en español.
Canal: {channel['name']} | Nicho: {channel['niche']} | Tono: {channel['tone']}
Tema: {topic_data['topic']}
Gancho: {topic_data['hook']}
Puntos clave: {json.dumps(topic_data['key_points'], ensure_ascii=False)}

REGLAS OBLIGATORIAS PARA LOS SLIDES:
1. MÁXIMO 25 caracteres por slide (esto es CRÍTICO, cuenta los caracteres)
2. Cada slide = 3 segundos de duración
3. 7-9 slides en total (25-30 segundos de video)
4. NO usar emojis en los slides (se ven mal en video)
5. CADA slide debe dar INFO CONCRETA — nombres, números, pasos
6. NO slides genéricos como "Esto te sorprendera" → di QUÉ te sorprenderá
7. Si el tema es "3 herramientas" → nombra las 3 en slides separados
8. Último slide: "Sigueme para mas" (sin emoji)

EJEMPLO DE SLIDES BUENOS (canal IA):
- "Quita fondos GRATIS?"
- "Se llama Remove.bg"
- "Subes tu foto"
- "En 2 segundos listo"
- "100% gratis"
- "Mejor que Photoshop"
- "Sigueme para mas"

EJEMPLO DE SLIDES MALOS (NO hacer esto):
- "La IA es increible" ← vacío, no dice nada
- "Esto cambiara todo" ← genérico
- "No te lo vas a creer" ← relleno

Responde SOLO con JSON válido:
{{
  "title": "titulo SEO max 60 chars con 1 emoji al inicio",
  "description": "descripcion 3 lineas con keywords y hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "text_slides": [
    {{"text": "Slide con info real", "duration": 3}},
    {{"text": "Dato concreto", "duration": 3}}
  ],
  "video_prompt": "dynamic shot related to topic, vertical 9:16, vibrant colors"
}}"""

    data = _call_with_fallback(prompt, primary="github", temperature=0.7)
    log.info("Título: %s", data["title"])
    return data
