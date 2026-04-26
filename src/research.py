"""
Investigación de tendencias y generación de contenido.
- Groq (Llama 3.3 70B): investiga tendencias (rápido, creativo)
- GitHub Models (DeepSeek-V3): genera contenido SEO (preciso, estructurado)
- Fallback cruzado: si uno falla, usa el otro
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
    """Llama a Groq API y devuelve JSON parseado."""
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return json.loads(response.choices[0].message.content)


def _call_github(prompt: str, temperature: float = 0.8) -> dict:
    """Llama a GitHub Models API y devuelve JSON parseado."""
    response = github_client.chat.completions.create(
        model=GITHUB_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    text = response.choices[0].message.content
    # Limpiar posible markdown ```json ... ```
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def _call_with_fallback(prompt: str, primary: str = "groq", temperature: float = 0.9) -> dict:
    """Intenta con primary, si falla usa fallback."""
    funcs = {"groq": _call_groq, "github": _call_github}
    fallback = "github" if primary == "groq" else "groq"

    try:
        return funcs[primary](prompt, temperature)
    except Exception as e:
        log.warning("%s falló: %s. Intentando %s...", primary, e, fallback)
        return funcs[fallback](prompt, temperature)


def research_topic(channel: dict) -> dict:
    """Investiga tema trending para el nicho del canal."""
    prompt = f"""Eres un investigador de tendencias de YouTube en español.
Canal: {channel['name']}
Nicho: {channel['niche']}
Tono: {channel['tone']}
Temas posibles: {', '.join(channel['topics'])}

Busca un tema que funcione como YouTube Short viral (vertical, máx 60 segundos).
El tema debe:
- Ser relevante y atractivo en 2026
- Enganchar en los primeros 3 segundos
- Poder explicarse en 5-7 frases cortas y potentes
- NO repetir temas genéricos — busca ángulos únicos o datos sorprendentes

Responde SOLO con JSON válido (sin markdown, sin explicaciones):
{{
  "topic": "tema concreto elegido",
  "hook": "pregunta o dato impactante para los primeros 3 segundos",
  "key_points": ["punto 1", "punto 2", "punto 3", "punto 4", "punto 5"],
  "search_terms": ["término búsqueda video en inglés 1", "término 2", "término 3"]
}}"""

    data = _call_with_fallback(prompt, primary="groq", temperature=1.0)
    log.info("Tema elegido: %s", data["topic"])
    return data


def generate_content(channel: dict, topic_data: dict) -> dict:
    """Genera título SEO, descripción, tags, slides de texto y prompt de video."""
    prompt = f"""Genera contenido completo para un YouTube Short en español.
Canal: {channel['name']} | Nicho: {channel['niche']} | Tono: {channel['tone']}
Tema: {topic_data['topic']}
Gancho: {topic_data['hook']}
Puntos clave: {json.dumps(topic_data['key_points'], ensure_ascii=False)}

Requisitos:
- Título SEO: máximo 70 caracteres, con keywords, que genere curiosidad
- Descripción: máximo 500 caracteres, con keywords naturales, incluir CTA
- Tags: 8-12 tags relevantes en español
- text_slides: 5-7 diapositivas de texto para superponer en el video
  - Cada slide: texto corto (máx 60 caracteres), duración en segundos
  - Primera slide = gancho (3-4 segundos)
  - Última slide = CTA o reflexión final (4 segundos)
  - Total duración entre 30-55 segundos
- video_prompt: prompt en INGLÉS para generar video con IA (escena visual, no texto)

Responde SOLO con JSON válido (sin markdown, sin explicaciones):
{{
  "title": "título SEO aquí",
  "description": "descripción con keywords y CTA",
  "tags": ["tag1", "tag2"],
  "text_slides": [
    {{"text": "¿Sabías que...?", "duration": 4}},
    {{"text": "Dato importante", "duration": 5}}
  ],
  "video_prompt": "cinematic shot of..."
}}"""

    data = _call_with_fallback(prompt, primary="github", temperature=0.8)
    log.info("Título: %s", data["title"])
    return data
