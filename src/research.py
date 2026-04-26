"""
Investigación de tendencias y generación de contenido VIRAL.
Optimizado para máxima retención en YouTube Shorts.
- Groq (Llama 3.3 70B): investiga tendencias
- GitHub Models (DeepSeek-V3): genera contenido SEO
- Fallback cruzado
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


def research_topic(channel: dict) -> dict:
    """Investiga tema trending VIRAL para Shorts."""
    prompt = f"""Eres un experto en YouTube Shorts virales en español.
Canal: {channel['name']}
Nicho: {channel['niche']}
Tono: {channel['tone']}
Temas posibles: {', '.join(channel['topics'])}

IMPORTANTE — Esto es para un Short VIRAL. El tema debe:
- Provocar reacción emocional INMEDIATA (sorpresa, curiosidad, indignación, "¡no sabía esto!")
- Ser algo que la gente quiera compartir
- Tener un ángulo polémico o dato IMPACTANTE
- Funcionar con la fórmula: HOOK → TENSIÓN → REVELACIÓN

Responde SOLO con JSON válido:
{{
  "topic": "tema concreto con ángulo viral",
  "hook": "frase GANCHO de máx 8 palabras que pare el scroll (pregunta provocadora o dato shocking)",
  "key_points": ["dato 1 impactante", "dato 2", "dato 3", "dato 4", "conclusión memorable"],
  "search_terms": ["búsqueda video en inglés 1", "término 2", "término 3"]
}}"""

    data = _call_with_fallback(prompt, primary="groq", temperature=1.0)
    log.info("Tema elegido: %s", data["topic"])
    return data


def generate_content(channel: dict, topic_data: dict) -> dict:
    """Genera contenido optimizado para RETENCIÓN y viralidad."""
    prompt = f"""Genera contenido para un YouTube Short VIRAL en español.
Canal: {channel['name']} | Nicho: {channel['niche']} | Tono: {channel['tone']}
Tema: {topic_data['topic']}
Gancho: {topic_data['hook']}
Puntos clave: {json.dumps(topic_data['key_points'], ensure_ascii=False)}

REGLAS PARA SHORTS VIRALES:
1. Duración total: 25-35 segundos (sweet spot viral)
2. HOOK en slide 1: máx 8 palabras, que pare el scroll
3. Cada slide: MÁXIMO 2-3 segundos, texto CORTO (máx 40 caracteres)
4. Ritmo RÁPIDO — sin pausas, sin relleno
5. Estructura: Hook → Tensión → Datos → Revelación → CTA loop
6. Última slide debe conectar con la primera (loop = más reproducciones)
7. Usar MAYÚSCULAS para palabras clave
8. Emojis estratégicos (1-2 por slide máximo)

Responde SOLO con JSON válido:
{{
  "title": "título clickbait SEO máx 60 chars (con emoji + mayúsculas estratégicas)",
  "description": "descripción 3 líneas con keywords, CTA y hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "text_slides": [
    {{"text": "¿Sabías ESTO? 🤯", "duration": 2}},
    {{"text": "Dato impactante", "duration": 2.5}},
    {{"text": "Otro dato", "duration": 2.5}},
    {{"text": "Revelación FINAL", "duration": 3}},
    {{"text": "Sígueme para más 👆", "duration": 2}}
  ],
  "video_prompt": "dynamic cinematic shot, fast movement, vibrant colors, vertical 9:16..."
}}"""

    data = _call_with_fallback(prompt, primary="github", temperature=0.8)
    log.info("Título: %s", data["title"])
    return data
