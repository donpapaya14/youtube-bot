"""
Genera guiones con VALOR REAL para YouTube Shorts narrados.
Cada Short enseña algo CONCRETO con voz + texto.
"""

import json
import logging
import os
import random
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


CONTENT_FORMULAS = {
    "finanzas": [
        "Un truco de ahorro concreto con pasos exactos y cifras reales en euros",
        "Una app gratuita REAL para gestionar dinero: nombre, cómo se usa, qué hace",
        "Un error financiero específico que te cuesta X euros al año con ejemplo numérico",
    ],
    "legal": [
        "Un derecho del consumidor específico con artículo de ley y ejemplo de uso real",
        "Qué hacer paso a paso si te echan del trabajo (pasos concretos y plazos)",
        "Un truco legal que pocos conocen para reclamar dinero con resultado real",
    ],
    "ia": [
        "Una herramienta de IA gratuita REAL con su nombre, URL y demostración de uso paso a paso",
        "Un prompt EXACTO (palabra por palabra) para ChatGPT que resuelve un problema concreto del día a día",
        "Una función oculta de ChatGPT, Gemini o Claude que casi nadie conoce con instrucciones exactas",
    ],
    "salud": [
        "Un hallazgo científico de una universidad real con nombre del estudio y dato medible",
        "Una rutina de 5 minutos con pasos numerados y beneficio demostrado por ciencia",
        "Un alimento específico con beneficio concreto respaldado por estudio real",
    ],
    "negocio": [
        "Un caso de éxito real: persona o empresa que logró X con método específico y cifras",
        "Una estrategia de ventas concreta con 3 pasos numerados que puedes aplicar hoy",
        "Una herramienta gratuita REAL para emprendedores con nombre y para qué sirve exactamente",
    ],
}

NICHE_MAP = {
    "FinanzasClara": "finanzas",
    "MenteLegal": "legal",
    "IAExplica": "ia",
    "SaludLongevidad": "salud",
    "MentePróspera": "negocio",
}


def research_topic(channel: dict) -> dict:
    niche_key = NICHE_MAP.get(channel["name"], "ia")
    formulas = CONTENT_FORMULAS.get(niche_key, CONTENT_FORMULAS["ia"])
    formula = random.choice(formulas)

    prompt = f"""Eres un guionista de YouTube Shorts educativos en español con 10M de seguidores.
Canal: {channel['name']} | Nicho: {channel['niche']}

CREA UN GUIÓN SOBRE: {formula}

REGLAS:
- Todo REAL y VERIFICABLE. Nombres reales de herramientas, leyes, estudios
- Si mencionas una herramienta, da su NOMBRE REAL
- Si mencionas un dato, da la CIFRA REAL
- Si mencionas un estudio, di DE DÓNDE es
- CERO relleno, CERO frases vacías

Responde JSON:
{{
  "topic": "tema concreto",
  "hook": "frase gancho de 8 palabras máximo",
  "key_points": ["dato real 1", "dato real 2", "dato real 3", "dato real 4"],
  "search_terms": ["búsqueda en inglés 1", "término 2", "término 3"]
}}"""

    data = _call_with_fallback(prompt, primary="groq", temperature=0.9)
    log.info("Tema: %s", data["topic"])
    return data


def generate_content(channel: dict, topic_data: dict) -> dict:
    """Genera guión narrado con texto en pantalla."""
    prompt = f"""Escribe un guión para un YouTube Short NARRADO de 30 segundos en español.
Canal: {channel['name']} | Tono: {channel['tone']}
Tema: {topic_data['topic']}
Gancho: {topic_data['hook']}
Datos clave: {json.dumps(topic_data['key_points'], ensure_ascii=False)}

FORMATO: El Short tiene VOZ narrando + TEXTO en pantalla.
- "voice" = lo que dice la voz (frase natural, como hablando a un amigo)
- "text" = texto corto que aparece en pantalla (MÁXIMO 20 caracteres, resumen visual)

REGLAS:
1. 7-9 segmentos
2. Voz natural, directa, como contándole algo a un amigo
3. Texto en pantalla = resumen ultra corto de lo que dice la voz
4. PRIMER segmento = gancho que para el scroll
5. ÚLTIMO segmento = "Sígueme para más tips"
6. Sin emojis en el texto (se ven mal en video)
7. Sin frases vacías. Cada segmento aporta INFO NUEVA
8. Hablar de TÚ al espectador

EJEMPLO BUENO (canal IA):
[
  {{"voice": "¿Sabías que hay una IA que te escribe emails perfectos gratis?", "text": "Emails con IA?", "duration": 4}},
  {{"voice": "Se llama Compose AI y es una extensión de Chrome", "text": "Compose AI", "duration": 3}},
  {{"voice": "La instalas, abres Gmail, y cuando empiezas a escribir", "text": "Abres Gmail", "duration": 3}},
  {{"voice": "la IA te sugiere el email completo en segundos", "text": "Email en segundos", "duration": 3}},
  {{"voice": "Es completamente gratis y ya la usan 2 millones de personas", "text": "2M de usuarios", "duration": 3}},
  {{"voice": "Yo la uso todos los días y me ahorra media hora", "text": "30 min ahorrados", "duration": 3}},
  {{"voice": "Sígueme para descubrir más herramientas como esta", "text": "Sigueme", "duration": 3}}
]

Responde SOLO JSON:
{{
  "title": "titulo SEO max 60 chars con 1 emoji",
  "description": "descripcion 3 lineas con keywords y CTA. Incluir link newsletter.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "segments": [
    {{"voice": "texto voz natural", "text": "RESUMEN corto", "duration": 3}},
    ...
  ],
  "video_prompt": "visual description for stock footage search"
}}"""

    data = _call_with_fallback(prompt, primary="github", temperature=0.7)
    log.info("Título: %s", data["title"])
    return data
