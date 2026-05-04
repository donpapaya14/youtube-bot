"""
Genera guiones con VALOR REAL para YouTube Shorts narrados.
Cada Short enseña algo CONCRETO con voz + texto.
"""

import json
import logging
import os
import random
import re as _re
import time
from groq import Groq
from openai import OpenAI

log = logging.getLogger(__name__)

NVIDIA_FAST = "deepseek-ai/deepseek-v4-flash"
NVIDIA_STABLE = "meta/llama-3.3-70b-instruct"
GROQ_MODEL = "llama-3.3-70b-versatile"
GITHUB_MODEL = "DeepSeek-V3-0324"


def _parse_json(text: str) -> dict:
    """Limpia markdown/think tags y parsea JSON."""
    text = text.strip()
    if "<think>" in text:
        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def _call_nvidia(prompt: str, temperature: float = 0.9) -> dict:
    """NVIDIA: intenta v4-flash (rápido), si 504 → llama-3.3 (estable)."""
    key = os.getenv("NVIDIA_API_KEY")
    if not key:
        raise ValueError("NVIDIA_API_KEY no configurada")
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=key,
        timeout=90.0,
        max_retries=0,
    )
    try:
        response = client.chat.completions.create(
            model=NVIDIA_FAST,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=4096,
        )
        return _parse_json(response.choices[0].message.content)
    except Exception as e:
        log.warning("NVIDIA v4-flash: %s → probando llama-3.3", str(e)[:60])

    response = client.chat.completions.create(
        model=NVIDIA_STABLE,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=4096,
    )
    return _parse_json(response.choices[0].message.content)


def _call_groq(prompt: str, temperature: float = 0.9) -> dict:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY no configurada")
    client = Groq(api_key=key, timeout=60.0, max_retries=0)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return json.loads(response.choices[0].message.content)


def _call_github(prompt: str, temperature: float = 0.8) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN no configurado")
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=token,
        timeout=120.0,
        max_retries=0,
    )
    response = client.chat.completions.create(
        model=GITHUB_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=4096,
    )
    return _parse_json(response.choices[0].message.content)


_PROVIDER_MAP = {
    "groq": _call_groq,
    "github": _call_github,
    "nvidia": _call_nvidia,
}

PROVIDERS = ["groq", "github", "nvidia"]


def _call_with_fallback(prompt: str, primary: str = "groq", temperature: float = 0.9) -> dict:
    """Llama al proveedor primario y cae a los demás si falla. Fallback inmediato."""
    # Build order: primary first, then the rest
    order = [primary] + [p for p in PROVIDERS if p != primary]

    errors = []
    for name in order:
        func = _PROVIDER_MAP[name]
        try:
            result = func(prompt, temperature)
            log.info("✓ %s", name)
            return result
        except Exception as e:
            err = str(e)
            errors.append(f"{name}: {err[:100]}")
            log.warning("✗ %s: %s", name, err[:100])
            if "429" in err:
                time.sleep(15)
            else:
                time.sleep(3)

    raise RuntimeError(f"Todos los proveedores fallaron: {'; '.join(errors)}")


CONTENT_FORMULAS = {
    "finanzas": [
        # MICRO-NICHO 1: Autónomos España
        "Un truco fiscal REAL para autónomos en España: deducción concreta con artículo de ley y cifra exacta de ahorro anual",
        "Un error que cometen el 80% de autónomos en España con Hacienda: qué hacen mal, cuánto les cuesta, y cómo evitarlo paso a paso",
        "Una cuota o gasto que los autónomos pagan de más sin saberlo: cifra real, alternativa legal, pasos para reclamar",
        # MICRO-NICHO 2: Ahorro con sueldo bajo
        "Un truco de ahorro REAL para quien gana menos de 1.500€/mes: cifra exacta de ahorro mensual con ejemplo del día a día en España",
        "Un gasto hormiga concreto que te cuesta más de 500€ al año sin darte cuenta: cálculo real y alternativa gratuita",
        "Un método de presupuesto específico para sueldos bajos con ejemplo real de distribución de un sueldo de 1.200€",
        # MICRO-NICHO 3: Trucos de Hacienda
        "Una deducción de la declaración de la renta que el 90% de españoles no aplica: artículo de ley, requisitos y cifra de ahorro",
        "Un truco LEGAL para pagar menos IRPF este año: paso a paso con cifras reales y base legal",
        "Un derecho frente a Hacienda que pocos conocen: qué puedes reclamar, cómo hacerlo y plazo exacto",
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
    "salud_longevidad": [
        "Un hallazgo científico sobre longevidad de una universidad real con nombre del estudio y dato medible",
        "Un hábito diario que extiende la esperanza de vida con estudio real y cifra concreta",
        "Un biomarcador de envejecimiento que puedes medir y mejorar con datos científicos",
    ],
    "salud_bienestar": [
        "Una rutina de bienestar de 5 minutos con pasos numerados y beneficio demostrado por ciencia",
        "Un alimento específico con beneficio concreto respaldado por estudio real de nutrición",
        "Un hábito matutino que mejora tu energía todo el día con explicación neurocientífica",
    ],
    "negocio": [
        "Un caso de éxito real: persona o empresa que logró X con método específico y cifras",
        "Una estrategia de ventas concreta con 3 pasos numerados que puedes aplicar hoy",
        "Una herramienta gratuita REAL para emprendedores con nombre y para qué sirve exactamente",
    ],
}

NICHE_MAP = {
    "FinanzasClara": "finanzas",
    "SaludLongevidad": "salud_longevidad",
    "VidaSana360": "salud_bienestar",
    "CatBrothers": "gatos",
    "HogarInteligente": "hogar",
}

CONTENT_FORMULAS["gatos"] = [
    "Un dato curioso sobre gatos que la mayoría no sabe, con fuente científica real",
    "Una raza de gato poco conocida con características únicas y datos reales de la raza",
    "Un comportamiento de gatos explicado científicamente: por qué hacen X",
    "Un alimento que los gatos NO deben comer con nivel de toxicidad real según ASPCA",
    "Un juguete casero para gatos con materiales de casa y por qué les encanta",
    "Una señal de enfermedad en gatos que los dueños ignoran, con datos de veterinarios",
    "Un mito sobre gatos que es completamente falso, con estudio que lo desmiente",
    "Una diferencia entre gatos domésticos y salvajes que explica un comportamiento concreto",
    "Un truco de adiestramiento felino que funciona según la ciencia del comportamiento animal",
    "Una planta tóxica para gatos que muchos tienen en casa, con nivel de peligro según ASPCA",
    "Un dato sobre la visión, oído o olfato de los gatos comparado con humanos, con cifras reales",
    "Un error común en la alimentación de gatos que causa problemas de salud a largo plazo",
    "Una curiosidad sobre los ronroneos de los gatos: frecuencia exacta y beneficios demostrados",
    "Un tipo de arena para gatos que es mejor según estudios veterinarios y por qué",
    "Una historia real de un gato famoso (Félicette, Unsinkable Sam, etc.) con datos verificables",
]

CONTENT_FORMULAS["hogar"] = [
    "Un truco de limpieza casero con ingredientes comunes (vinagre, bicarbonato, limón) y la ciencia de por qué funciona",
    "Un dato curioso sobre el hogar que la mayoría no sabe, con fuente o estudio real",
    "Un truco para ahorrar energía en casa con cifra real de cuánto ahorras al año en euros",
    "Un hack de organización del hogar con método concreto y pasos numerados que puedes aplicar hoy",
    "Un error doméstico común que te cuesta dinero o salud con dato verificable y solución práctica",
    "Un electrodoméstico que gastas mal sin saberlo: consumo real en kWh y cómo optimizarlo",
    "Un truco para eliminar un olor concreto del hogar con la química de por qué funciona",
    "Un material de cocina que deberías dejar de usar según estudios de seguridad alimentaria",
    "Una forma de organizar el frigorífico que reduce desperdicio alimentario con datos de la FAO",
    "Un truco de fontanería casera que te ahorra llamar al técnico, paso a paso",
    "Una temperatura ideal para cada habitación según la OMS y cuánto ahorras ajustándola",
    "Un producto de limpieza que NUNCA debes mezclar con otro: reacción química peligrosa",
    "Un hack para que la ropa dure más basado en ciencia textil real",
    "Un truco para reducir humedad en casa sin deshumidificador con explicación física",
    "Un error al cargar el lavavajillas que reduce su eficacia un 40% según fabricantes",
]

CONTENT_FORMULAS["salud_longevidad"].extend([
    "Un suplemento con evidencia real de beneficio en longevidad con dosis y estudio publicado",
    "Un error común que acorta la vida con dato estadístico y alternativa saludable respaldada",
    "Un descubrimiento reciente sobre envejecimiento celular con nombre de investigadores y universidad",
    "Un alimento de las zonas azules que extiende la vida con datos epidemiológicos reales",
    "Un marcador sanguíneo que predice longevidad y cómo mejorarlo según estudios clínicos",
    "Un tipo de ejercicio que revierte el envejecimiento según estudios de telómeros",
    "Un patrón de sueño específico asociado a mayor esperanza de vida con datos de cohortes",
    "Una técnica de gestión del estrés con impacto medible en biomarcadores de envejecimiento",
    "Un hábito social que aumenta la esperanza de vida más que el ejercicio según Harvard",
    "Una vitamina o mineral cuyo déficit acelera el envejecimiento con dosis óptima según estudios",
    "Un descubrimiento sobre la microbiota intestinal y longevidad con universidad y año del estudio",
    "Un protocolo de ayuno con evidencia en longevidad: tipo, duración y estudio que lo respalda",
])

CONTENT_FORMULAS["salud_bienestar"].extend([
    "Un truco de pérdida de peso respaldado por un estudio real con nombre de universidad y cifra concreta",
    "Un error de dieta muy común con explicación científica de por qué NO funciona y qué hacer en su lugar",
    "Un ejercicio específico que quema más calorías que correr con datos medibles de un estudio real",
    "Un alimento que reduce la inflamación con mecanismo biológico y estudio concreto",
    "Un hábito de hidratación que mejora un aspecto concreto de la salud con cifras",
    "Una técnica de respiración con beneficio demostrado en presión arterial o cortisol",
    "Un mito de nutrición popular que es falso según meta-análisis con nombre del estudio",
    "Un snack saludable que sacia más que otros con datos de índice de saciedad",
    "Una rutina de estiramientos de 3 minutos que mejora un dolor concreto según fisioterapeutas",
    "Un momento del día óptimo para hacer ejercicio según cronobiología con estudio real",
    "Un tipo de fibra específica con beneficio concreto para el intestino según gastroenterólogos",
    "Un error al dormir que arruina la calidad del sueño con datos de polisomnografía",
])


def _get_recent_titles(channel: dict) -> list[str]:
    """Obtiene títulos recientes del canal YouTube para evitar duplicados."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build as yt_build

        token_env = channel.get("refresh_token_env", "YOUTUBE_REFRESH_TOKEN")
        refresh_token = os.getenv(token_env)
        if not refresh_token:
            log.warning("Sin refresh token para dedup, continuando sin historial")
            return []

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("YOUTUBE_CLIENT_ID"),
            client_secret=os.getenv("YOUTUBE_CLIENT_SECRET"),
            scopes=["https://www.googleapis.com/auth/youtube"],
        )

        youtube = yt_build("youtube", "v3", credentials=creds)

        # Obtener playlist de uploads del canal
        ch_resp = youtube.channels().list(part="contentDetails", mine=True).execute()
        if not ch_resp.get("items"):
            return []

        uploads_id = ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Obtener últimos 50 videos
        pl_resp = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_id,
            maxResults=50,
        ).execute()

        titles = [item["snippet"]["title"] for item in pl_resp.get("items", [])]
        log.info("Dedup: %d títulos recientes obtenidos del canal", len(titles))
        return titles
    except Exception as e:
        log.warning("Dedup: no se pudieron obtener títulos: %s", str(e)[:100])
        return []


# ── Local title cache (evita race condition entre crons del mismo día) ──

def _local_cache_path(channel_name: str) -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_dir = os.path.join(project_root, ".title_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{channel_name}.txt")


def _load_local_titles(channel_name: str) -> list[str]:
    """Carga títulos del cache local (últimos 60 días)."""
    path = _local_cache_path(channel_name)
    if not os.path.exists(path):
        return []
    titles = []
    cutoff = time.time() - 60 * 86400  # 60 días
    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if "|" not in line:
                continue
            ts_str, title = line.split("|", 1)
            try:
                ts = float(ts_str)
            except ValueError:
                continue
            if ts > cutoff:
                titles.append(title)
                lines.append(line)
    # Reescribir solo líneas no expiradas
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n" if lines else "")
    return titles


def _save_local_title(channel_name: str, title: str):
    """Guarda título en cache local con timestamp."""
    path = _local_cache_path(channel_name)
    with open(path, "a") as f:
        f.write(f"{time.time()}|{title}\n")


def _is_duplicate(new_title: str, existing_titles: list[str], threshold: float = 0.5) -> bool:
    """Check si título es demasiado similar a uno existente (word overlap)."""
    new_words = set(_re.sub(r"[^\w\s]", "", new_title.lower()).split())
    if len(new_words) < 2:
        return False
    for existing in existing_titles:
        existing_words = set(_re.sub(r"[^\w\s]", "", existing.lower()).split())
        if len(existing_words) < 2:
            continue
        overlap = len(new_words & existing_words)
        similarity = overlap / min(len(new_words), len(existing_words))
        if similarity >= threshold:
            log.warning("Duplicado detectado (%.0f%%): '%s' ≈ '%s'", similarity * 100, new_title[:40], existing[:40])
            return True
    return False


CHANNEL_TOPICS_MAP = {
    "VidaSana360": "vidasana360.json",
    "SaludLongevidad": "saludlongevidad.json",
    "CatBrothers": "catbrothers.json",
    "HogarInteligente": "hogarinteligente.json",
    "FinanzasClara": "finanzasclara.json",
}

# Canales que comparten nicho — cross-channel dedup
SIBLING_CHANNELS = {
    "VidaSana360": {"name": "SaludLongevidad", "refresh_token_env": "YT_TOKEN_SALUD"},
    "SaludLongevidad": {"name": "VidaSana360", "refresh_token_env": "YT_TOKEN_PRINCIPAL"},
}


def _load_prewritten_topic(channel: dict) -> dict | None:
    """Carga un tema pre-escrito del banco, marcándolo como usado."""
    topics_file = CHANNEL_TOPICS_MAP.get(channel["name"])
    if not topics_file:
        return None

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "topics", topics_file)

    if not os.path.exists(path):
        return None

    try:
        with open(path) as f:
            topics = json.load(f)

        # Merge con archivo _extra si existe
        extra_path = path.replace(".json", "_extra.json")
        if os.path.exists(extra_path):
            with open(extra_path) as f:
                topics.extend(json.load(f))

        # Cargar IDs ya usados
        used_file = path + ".used"
        used_ids = set()
        if os.path.exists(used_file):
            with open(used_file) as f:
                used_ids = {int(x.strip()) for x in f.read().strip().split("\n") if x.strip()}

        # Obtener títulos recientes para dedup extra (propio + hermanos)
        recent_titles = _get_recent_titles(channel)
        sibling = SIBLING_CHANNELS.get(channel["name"])
        if sibling:
            try:
                recent_titles.extend(_get_recent_titles(sibling))
            except Exception:
                pass
        recent_lower = {t.lower() for t in recent_titles}

        # Filtrar disponibles
        available = [t for t in topics if t["id"] not in used_ids]
        if not available:
            log.info("Banco de temas agotado para %s, usando AI", channel["name"])
            return None

        # Evitar temas similares a videos recientes
        best = None
        for t in available:
            topic_lower = t["topic"].lower()
            if not any(topic_lower[:20] in rt or rt[:20] in topic_lower for rt in recent_lower):
                best = t
                break
        if not best:
            best = random.choice(available)

        # Marcar como usado
        with open(used_file, "a") as f:
            f.write(str(best["id"]) + "\n")

        log.info("Tema pre-escrito #%d: %s", best["id"], best["topic"])
        return {
            "topic": best["topic"],
            "hook": best["hook"],
            "key_points": best["key_points"],
            "search_terms": best["search_terms"],
        }
    except Exception as e:
        log.warning("Error cargando banco de temas: %s", str(e)[:100])
        return None


def _collect_all_titles(channel: dict) -> list[str]:
    """Combina títulos de YouTube API + cache local + canales hermanos."""
    titles = _get_recent_titles(channel)
    # Cache local (cubre race condition entre crons del mismo día)
    local = _load_local_titles(channel["name"])
    titles.extend(local)
    # Canales hermanos
    sibling = SIBLING_CHANNELS.get(channel["name"])
    if sibling:
        try:
            sibling_titles = _get_recent_titles(sibling)
            titles.extend(sibling_titles)
            titles.extend(_load_local_titles(sibling["name"]))
            log.info("Cross-dedup: +%d títulos de %s", len(sibling_titles), sibling["name"])
        except Exception as e:
            log.warning("Cross-dedup falló para %s: %s", sibling["name"], str(e)[:60])
    # Dedup lista
    return list(set(titles))


def research_topic(channel: dict) -> dict:
    all_titles = _collect_all_titles(channel)

    # 1. Intentar tema pre-escrito primero (mayor calidad)
    prewritten = _load_prewritten_topic(channel)
    if prewritten:
        if not _is_duplicate(prewritten["topic"], all_titles):
            _save_local_title(channel["name"], prewritten["topic"])
            return prewritten
        log.warning("Tema pre-escrito duplicado, generando con AI")

    # 2. Fallback: generar con AI + hard dedup (hasta 3 intentos)
    niche_key = NICHE_MAP.get(channel["name"], "salud_bienestar")
    formulas = CONTENT_FORMULAS.get(niche_key, CONTENT_FORMULAS["salud_bienestar"])

    if all_titles:
        avoid_str = "\n".join(f"- {t}" for t in all_titles[-50:])
    else:
        avoid_str = "(sin historial disponible)"

    # Shuffle formulas para no repetir la misma
    shuffled = formulas[:]
    random.shuffle(shuffled)

    for attempt in range(3):
        formula = shuffled[attempt % len(shuffled)]

        # Enriquecer con tendencias actuales
        try:
            from trending import enrich_prompt_with_trends
            formula = enrich_prompt_with_trends(formula, niche_key)
        except Exception:
            pass

        prompt = f"""Eres un guionista de YouTube Shorts educativos en español con 10M de seguidores.
Canal: {channel['name']} | Nicho: {channel['niche']}

CREA UN GUIÓN SOBRE: {formula}

VIDEOS YA PUBLICADOS EN ESTE CANAL Y CANALES HERMANOS (NO REPITAS estos temas ni hagas variaciones similares):
{avoid_str}

REGLAS:
- Todo REAL y VERIFICABLE. Nombres reales de herramientas, leyes, estudios
- Si mencionas una herramienta, da su NOMBRE REAL
- Si mencionas un dato, da la CIFRA REAL
- Si mencionas un estudio, di DE DÓNDE es
- CERO relleno, CERO frases vacías
- El tema DEBE ser COMPLETAMENTE diferente a todos los videos listados arriba
- OBLIGATORIO: elige un ángulo ÚNICO que no aparezca en la lista

Responde JSON:
{{
  "topic": "tema concreto",
  "hook": "frase gancho de 8 palabras máximo",
  "key_points": ["dato real 1", "dato real 2", "dato real 3", "dato real 4"],
  "search_terms": ["búsqueda visual en inglés muy específica del tema para encontrar video de fondo 1", "término visual 2", "término visual 3"]
}}"""

        data = _call_with_fallback(prompt, primary="groq", temperature=min(0.9 + attempt * 0.1, 1.2))

        # HARD CHECK: verificar que no sea duplicado
        if not _is_duplicate(data["topic"], all_titles):
            _save_local_title(channel["name"], data["topic"])
            log.info("Tema (intento %d): %s", attempt + 1, data["topic"])
            return data

        log.warning("Intento %d: tema duplicado '%s', reintentando con otra fórmula", attempt + 1, data["topic"][:40])
        all_titles.append(data["topic"])  # Evitar regenerar el mismo

    # Si 3 intentos fallan, subir igual pero con warning
    _save_local_title(channel["name"], data["topic"])
    log.warning("DEDUP: 3 intentos fallaron, usando último resultado: %s", data["topic"][:50])
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
1. 7-8 segmentos
2. Cada frase de voz: MÁXIMO 15 palabras. Cortas, directas, sin subordinadas
3. Texto en pantalla = resumen ultra corto (máx 20 chars)
4. PRIMER segmento = gancho que para el scroll
5. ÚLTIMO segmento = CTA con URGENCIA y curiosidad. Ejemplos:
   - "Mañana subo algo que te va a cambiar [tema]. Suscríbete para no perdértelo"
   - "Si esto te ha servido, lo que viene mañana te va a sorprender. Dale a seguir"
   - "Esto es solo la punta del iceberg. Suscríbete, mañana viene lo mejor"
   NUNCA uses "Sígueme para más tips" — es genérico y no convierte
6. Sin emojis en el texto
7. CADA segmento aporta INFO NUEVA y CONCRETA
8. Hablar de TÚ al espectador
9. Duración total del video: 25-35 segundos MÁXIMO

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
  "description": "descripcion 3 lineas con keywords naturales y CTA al canal.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "segments": [
    {{"voice": "texto voz natural", "text": "RESUMEN corto", "duration": 3}},
    ...
  ],
  "video_prompt": "descripción visual específica para buscar video de fondo relacionado con el tema"
}}"""

    data = _call_with_fallback(prompt, primary="github", temperature=0.7)
    log.info("Título: %s", data["title"])
    return data
