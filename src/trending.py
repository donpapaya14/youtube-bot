"""
Detector de tendencias para YouTube Shorts.
Busca trending topics en Google Trends y YouTube,
y los inyecta en research.py para que los Shorts sigan tendencias.

Uso: importar desde research.py o ejecutar standalone para ver tendencias actuales.
"""

import json
import logging
import os
import random
import re
import urllib.request

log = logging.getLogger(__name__)


def get_google_trends_es() -> list[str]:
    """Obtiene tendencias de Google Trends España via RSS."""
    try:
        url = "https://trends.google.com/trending/rss?geo=ES"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        content = resp.read().decode("utf-8")
        # Extraer títulos del RSS
        titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", content)
        return titles[:20]
    except Exception as e:
        log.warning("Google Trends ES error: %s", str(e)[:80])
        return []


def get_google_trends_us() -> list[str]:
    """Obtiene tendencias de Google Trends USA."""
    try:
        url = "https://trends.google.com/trending/rss?geo=US"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        content = resp.read().decode("utf-8")
        titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", content)
        return titles[:20]
    except Exception as e:
        log.warning("Google Trends US error: %s", str(e)[:80])
        return []


def get_trending_for_niche(niche_key: str) -> str | None:
    """Devuelve un tema trending relevante para el nicho, o None si no hay."""
    trends = get_google_trends_es()
    if not trends:
        return None

    # Palabras clave por nicho para filtrar tendencias relevantes
    niche_keywords = {
        "finanzas": ["banco", "dinero", "ahorro", "hipoteca", "euro", "economía", "impuesto", "hacienda", "precio", "inflación", "salario", "pensión"],
        "salud": ["salud", "dieta", "ejercicio", "hospital", "médico", "enfermedad", "vacuna", "nutrición", "peso", "dormir", "estrés", "mental"],
        "gatos": ["gato", "mascota", "animal", "perro", "veterinario", "adopción"],
        "hogar": ["hogar", "casa", "cocina", "limpieza", "decoración", "gadget", "tecnología", "smart", "robot"],
    }

    keywords = niche_keywords.get(niche_key, [])
    if not keywords:
        return None

    # Buscar match
    for trend in trends:
        trend_lower = trend.lower()
        if any(kw in trend_lower for kw in keywords):
            return trend

    return None


def get_viral_format_suggestion(niche_key: str) -> str | None:
    """Sugiere un formato viral basado en tendencias actuales de Shorts."""
    # Formatos virales que rotan — actualizables
    viral_formats = {
        "finanzas": [
            "POV: descubres que puedes ahorrar X euros al mes con este truco",
            "3 cosas que la gente rica hace con su dinero que tú no",
            "El error financiero que el 90% de españoles comete",
            "Tu banco no quiere que sepas esto sobre las comisiones",
        ],
        "salud": [
            "Lo que pasa en tu cuerpo cuando dejas de comer X durante 7 días",
            "El alimento más sano del supermercado que nadie compra",
            "Un médico explica por qué no deberías hacer esto nunca",
            "3 señales de que tu cuerpo necesita más de este nutriente",
            "Come esto durante 1 semana y mira lo que pasa con tu piel",
        ],
        "gatos": [
            "Por qué tu gato hace esto cuando te mira fijamente",
            "La raza de gato que actúa más como un perro que como un gato",
            "Lo que tu gato intenta decirte con este comportamiento",
            "5 cosas que estresan a tu gato y no lo sabías",
        ],
        "hogar": [
            "El producto de Amazon que ha cambiado mi rutina de limpieza",
            "3 gadgets de cocina por menos de 15 euros que realmente funcionan",
            "El truco de limpieza viral que realmente funciona — probado",
            "Antes y después: organicé este espacio en 10 minutos con esto",
        ],
    }

    formats = viral_formats.get(niche_key, [])
    return random.choice(formats) if formats else None


def enrich_prompt_with_trends(base_formula: str, niche_key: str) -> str:
    """Enriquece el prompt de research.py con tendencias actuales."""
    enrichments = []

    # 1. Tema trending
    trending = get_trending_for_niche(niche_key)
    if trending:
        enrichments.append(f"TENDENCIA ACTUAL: '{trending}' es trending en España. Si puedes relacionar el tema con esta tendencia, hazlo de forma natural.")

    # 2. Formato viral
    viral = get_viral_format_suggestion(niche_key)
    if viral:
        enrichments.append(f"FORMATO VIRAL SUGERIDO: '{viral}'. Usa este estilo de gancho si encaja con el tema.")

    if enrichments:
        return base_formula + "\n\n" + "\n".join(enrichments)
    return base_formula


def main():
    """Muestra tendencias actuales (standalone)."""
    print("=== GOOGLE TRENDS ESPAÑA ===")
    for t in get_google_trends_es():
        print(f"  • {t}")

    print("\n=== GOOGLE TRENDS USA ===")
    for t in get_google_trends_us():
        print(f"  • {t}")

    print("\n=== TENDENCIAS POR NICHO ===")
    for niche in ["finanzas", "salud", "gatos", "hogar"]:
        trend = get_trending_for_niche(niche)
        print(f"  {niche}: {trend or 'ninguna'}")


if __name__ == "__main__":
    main()
