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

NVIDIA_FAST = "meta/llama-3.3-70b-instruct"
NVIDIA_STABLE = "mistralai/mistral-7b-instruct-v0.3"
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
    # Strip control characters that break json.loads (except \t \n \r)
    text = _re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
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
        # MICRO-NICHO 4: Inversión para principiantes
        "Una forma de invertir desde 10€/mes sin comisiones con nombre de plataforma real y rendimiento histórico",
        "Un error de inversión que comete el 90% de principiantes con cifra de cuánto dinero pierden por ello",
        "Una diferencia clave entre dos productos financieros que los bancos no te explican con datos reales",
        # MICRO-NICHO 5: Trucos bancarios
        "Un servicio bancario que estás pagando sin necesitarlo con cifra exacta y cómo cancelarlo",
        "Una cuenta o tarjeta sin comisiones con nombre real del banco y comparativa de ahorro anual",
        "Un truco para negociar con tu banco que funciona: qué decir exactamente y resultado esperado",
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
    # Spanish channels (legacy)
    "FinanzasClara": "finanzas",
    "SaludLongevidad": "salud_longevidad",
    "VidaSana360": "salud_bienestar",
    "CatBrothers": "cats_en",
    "HogarInteligente": "hogar",
    # English channels
    "MoneyClara": "finance_en",
    "LongevityLab": "longevity_en",
    "HealthSpark": "health_en",
    "HomeHacks": "home_en",
}

CONTENT_FORMULAS["finance_en"] = [
    "One specific bank fee 90% of people pay without knowing — exact amount and one sentence to get it removed",
    "A tax deduction most employees miss — specific rule, exact dollar/pound amount saved annually",
    "One budgeting method that works on any salary — specific steps and real example with numbers",
    "A credit card trick that saves real money — specific mechanic, average savings per year",
    "One investing mistake that costs beginners thousands — specific error with real percentage impact",
    "A savings hack that works automatically — specific app or method name with average monthly savings",
    "One number you must know about your pension/retirement — specific calculation with real example",
    "A legal way to reduce income tax that most people ignore — specific rule and exact savings",
    "One household subscription you're probably wasting money on — average annual cost and alternatives",
    "A negotiation script that lowers your bills — exact words to say and success rate from real data",
    "One compound interest fact that changes how you save — specific numbers over 10/20/30 years",
    "A free tool that tracks your money better than your bank app — specific name and best feature",
    "One salary negotiation tactic backed by HR research — specific phrase and average % increase",
    "A side income idea requiring zero investment — specific method with realistic monthly earnings",
    "One money rule from millionaires you can apply on any budget — specific rule with example",
]

CONTENT_FORMULAS["longevity_en"] = [
    "One longevity habit from Blue Zones backed by a specific population study — name of zone and measurable result",
    "A supplement that reduced biological age in a controlled trial — specific compound, dose and study citation",
    "One food that Harvard researchers link to longer lifespan — specific compound and mechanism",
    "A daily habit that extends telomere length according to peer-reviewed research — specific study and result",
    "One sleep optimization that improves cellular regeneration — specific technique and scientific mechanism",
    "A gut microbiome fact that changes what you should eat — specific bacteria, food source and health impact",
    "One fasting protocol with the strongest longevity evidence — specific hours, mechanism and study",
    "A stress reduction technique with measurable cortisol impact — specific method and percentage reduction",
    "One exercise type that outperforms others for longevity — specific study comparison with minutes/week",
    "A vitamin deficiency that accelerates aging in 40% of people — specific vitamin, test name and correction",
    "One anti-inflammatory food more powerful than ibuprofen for chronic inflammation — specific compound and dose",
    "A breathing technique that activates the vagus nerve — specific pattern and proven health benefits",
    "One biomarker of aging you can actually improve — specific test name and most effective intervention",
    "A circadian rhythm hack that improves sleep quality by measurable percentage — specific timing change",
    "One Mediterranean diet component with the strongest evidence for heart longevity — specific food and study",
]

CONTENT_FORMULAS["health_en"] = [
    "One science-backed fat loss trick most people ignore — specific mechanism and study result",
    "A morning habit that boosts energy all day — specific neuroscience explanation and timing",
    "One food that blocks fat absorption according to nutrition research — specific compound and amount",
    "A 5-minute exercise that burns more fat than 30-minute cardio — specific study and mechanism",
    "One hydration myth that's costing you energy — specific truth backed by sports science",
    "A protein timing rule that maximizes muscle building — specific window and amount from research",
    "One gut health habit that affects weight loss — specific bacteria and dietary change",
    "A common diet mistake that causes 80% of people to fail — specific psychological mechanism",
    "One metabolism booster with real evidence — specific food/habit and percentage improvement",
    "A sleep habit that cuts sugar cravings in half — specific sleep stage and hormonal mechanism",
    "One strength training fact that changes how you should work out — specific study comparison",
    "A cold exposure protocol with measurable metabolic benefits — specific temperature and duration",
    "One caloric density trick that makes you full on fewer calories — specific food swaps with numbers",
    "A posture correction that increases testosterone and reduces cortisol — specific study from Harvard",
    "One intermittent fasting variant with the best evidence for fat loss — specific protocol and result",
]

CONTENT_FORMULAS["home_en"] = [
    "One cleaning trick using only household ingredients that removes stubborn stains — specific chemistry",
    "A home hack that cuts electricity bill by specific percentage — average annual saving in dollars",
    "One organization method that saves 20 minutes every day — specific system with numbered steps",
    "A common home mistake that costs money or health — specific error, cost and solution",
    "One appliance you're using wrong that reduces its lifespan by years — specific mistake and fix",
    "A smell elimination trick that works permanently — specific cause and chemical solution",
    "One kitchen material you should stop using according to food safety studies — specific risk and alternative",
    "A fridge organization method that reduces food waste by 30% — specific zone system explained",
    "One simple plumbing fix that avoids calling a technician — step by step with cost saving",
    "A temperature setting in your home that saves the most energy — specific degrees and monthly saving",
    "One dangerous chemical combination in cleaning products — specific compounds and reaction explained",
    "A laundry trick that makes clothes last twice as long — specific science of fabric degradation",
    "One humidity reduction method without a dehumidifier — specific physics and materials needed",
    "A dishwasher loading mistake that reduces efficiency — specific position and energy impact",
    "One natural pest deterrent that actually works — specific compound, application method and evidence",
]

CONTENT_FORMULAS["cats_en"] = [
    "A cat behavior science fact most owners don't know — real study name and specific finding",
    "One food that's toxic to cats according to ASPCA — specific toxin, amount and symptoms",
    "A cat body language signal that means something surprising — specific behavior and what it really means",
    "One cat health symptom owners always miss — specific sign, condition it indicates and vet advice",
    "A cat breed fact that challenges the most common stereotype — specific trait backed by feline genetics",
    "One thing cats do that looks odd but is totally normal — specific behavior and evolutionary reason",
    "A cat nutrition mistake most owners make — specific error and what vets actually recommend",
    "One household plant that's deadly to cats — specific plant, toxic compound and risk level from ASPCA",
    "A cat sense fact compared to humans — specific numbers (vision range, hearing Hz, smell x-factor)",
    "One training trick that actually works on cats — specific method from animal behavior science",
    "A famous cat from history with a verifiable story — specific cat, dates and verified facts",
    "One cat purring fact that surprises everyone — specific Hz frequency and proven health benefit",
    "A cat sleeping habit explained by science — specific sleep stage, duration and feline biology",
    "One litter box mistake that causes behavioral problems — specific error and correction method",
    "A cat age conversion fact more accurate than the 7-year rule — specific formula and real biology",
]

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

        lang = channel.get("language", "es")
        if lang == "en":
            prompt = f"""You are a top YouTube Shorts scriptwriter with 10M subscribers.
Channel: {channel['name']} | Niche: {channel['niche']}

CREATE A SHORT ABOUT: {formula}

ALREADY PUBLISHED VIDEOS (DO NOT REPEAT these topics or similar variations):
{avoid_str}

RULES:
- Everything REAL and VERIFIABLE. Real tool names, real study citations, real numbers
- If you mention a tool, give its REAL NAME
- If you mention a stat, give the REAL NUMBER
- If you mention a study, say WHERE it's from
- ZERO filler, ZERO empty phrases
- Topic MUST be COMPLETELY different from all videos listed above
- MANDATORY: choose a UNIQUE angle not in the list

Respond JSON:
{{
  "topic": "specific topic in English",
  "hook": "MAX 8 words that STOPS THE SCROLL. Use surprise, specific stat or contradiction. Start with number, action verb or direct question. NEVER start with 'Discover' or 'Learn'. Ex: '90% of people make this money mistake', 'This habit adds 7 years to your life'",
  "key_points": ["real fact 1", "real fact 2", "real fact 3", "real fact 4"],
  "search_terms": ["very specific English visual search term for background footage 1", "term 2", "term 3"]
}}"""
        else:
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
  "hook": "frase de MÁXIMO 8 palabras que PARA EL SCROLL. Usa sorpresa, dato concreto o contradicción. Empieza con número, verbo de acción o pregunta directa. NUNCA empieces con 'Descubre' o 'Aprende'. Ej: 'El 80% de españoles comete este error', 'Esto te cuesta 300€ al año sin saberlo'",
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
    """Genera guión con texto en pantalla (español o inglés según canal)."""
    lang = channel.get("language", "es")

    if lang == "en":
        prompt = f"""Write a script for a 30-second YouTube Short with TEXT ON SCREEN (no voiceover).
Channel: {channel['name']} | Tone: {channel['tone']}
Topic: {topic_data['topic']}
Hook: {topic_data['hook']}
Key facts: {json.dumps(topic_data['key_points'], ensure_ascii=False)}

FORMAT: Text appears on screen over video. No voiceover.
- "voice" = what would be narrated (kept for reference, NOT recorded)
- "text" = SHORT text shown on screen (MAX 20 characters, visual summary)

RULES:
1. 7-8 segments
2. Each voice line: MAX 15 words. Short, direct, no complex clauses
3. On-screen text = ultra short (max 20 chars)
4. FIRST segment = scroll-stopping hook
5. LAST segment = CTA with URGENCY. Examples:
   - "Tomorrow I'm posting something that will change how you [topic]. Subscribe now"
   - "That's just the start. What I'm posting tomorrow will blow your mind. Follow"
   - "This is the tip of the iceberg. Subscribe — tomorrow gets even better"
   NEVER use "Follow for more tips" — too generic, doesn't convert
6. No emojis in text overlays
7. EVERY segment adds NEW and CONCRETE information
8. Speak directly to viewer (you/your)
9. Total video duration: 25-35 seconds MAX

GOOD EXAMPLE (finance channel):
[
  {{"voice": "90% of people are paying a bank fee they don't know exists", "text": "Hidden bank fee?", "duration": 4}},
  {{"voice": "It's called the maintenance fee — average 15 dollars a month", "text": "$15/month gone", "duration": 3}},
  {{"voice": "Call your bank and say: I want to waive my monthly fee", "text": "Say this exactly", "duration": 3}},
  {{"voice": "85% of people who ask get it removed immediately", "text": "85% success rate", "duration": 3}},
  {{"voice": "That's 180 dollars back in your pocket every year", "text": "$180/year saved", "duration": 3}},
  {{"voice": "Tomorrow I'm showing the fee that costs even more. Subscribe", "text": "Subscribe now", "duration": 3}}
]

Respond ONLY JSON:
{{
  "title": "YouTube search-optimized title, max 60 chars, include exact keyword people search (eg: 'how to lose belly fat', 'cat foods to avoid'), can be question or statement with specific stat, 1 emoji at start. NO generic clickbait",
  "description": "3 lines with natural keywords and channel CTA. In English.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "segments": [
    {{"voice": "natural narration text", "text": "SHORT overlay", "duration": 3}},
    ...
  ],
  "video_prompt": "very specific English visual description to find relevant background footage"
}}"""
    else:
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
5. ÚLTIMO segmento = CTA con URGENCIA y curiosidad
   NUNCA uses "Sígueme para más tips" — es genérico y no convierte
6. Sin emojis en el texto
7. CADA segmento aporta INFO NUEVA y CONCRETA
8. Hablar de TÚ al espectador
9. Duración total del video: 25-35 segundos MÁXIMO

Responde SOLO JSON:
{{
  "title": "titulo para YouTube búsqueda, max 60 chars, incluye la keyword exacta que alguien escribiría en el buscador, 1 emoji al inicio. NUNCA clickbait genérico sin contenido",
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
