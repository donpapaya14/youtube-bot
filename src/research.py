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

NVIDIA_FAST = "meta/llama-3.1-8b-instruct"
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
    # Strip control characters that break json.loads (except \t \n \r)
    text = _re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # strict=False allows control chars inside JSON strings
        return json.loads(text.strip(), strict=False)


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
        log.warning("NVIDIA fast (%s): %s → probando stable", NVIDIA_FAST, str(e)[:60])

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
    "FinanzasClara": "finance_en",
    "SaludLongevidad": "salud_longevidad",
    "VidaSana360": "health_en",
    "CatBrothers": "cats_en",
    "EspacioInteligente": "home_en",
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


_STOPWORDS = {
    # ES
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a", "en", "y", "o", "u",
    "que", "para", "por", "con", "sin", "es", "son", "ser", "este", "esta", "estos", "estas", "su", "sus",
    "lo", "le", "se", "te", "me", "mi", "tu", "como", "cuando", "donde", "porque", "tambien", "muy", "mas", "menos",
    "todo", "todos", "toda", "todas", "no", "si", "ya", "asi", "pero", "hay", "tiene", "tienen", "hacer",
    # EN
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "with", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "this", "that", "these", "those", "it", "its", "as", "by", "from", "have", "has",
    "do", "does", "did", "will", "would", "can", "could", "should", "may", "your", "you", "i", "we", "they", "he", "she",
    "what", "when", "where", "why", "how", "all", "any", "more", "less", "no", "not", "so", "if", "than", "then",
}


def _significant_words(title: str) -> set[str]:
    """Extrae palabras significativas: 4+ chars, no stopwords, sin números puros."""
    words = _re.sub(r"[^\w\s]", " ", title.lower()).split()
    return {w for w in words if len(w) >= 4 and w not in _STOPWORDS and not w.isdigit()}


def _is_duplicate(new_title: str, existing_titles: list[str], threshold: float = 0.35) -> bool:
    """Detecta duplicados con 3 capas: substring exacto, sustantivos compartidos, word overlap."""
    new_norm = _re.sub(r"\s+", " ", _re.sub(r"[^\w\s]", " ", new_title.lower())).strip()
    new_sig = _significant_words(new_title)

    if not new_sig:
        return False

    for existing in existing_titles:
        existing_norm = _re.sub(r"\s+", " ", _re.sub(r"[^\w\s]", " ", existing.lower())).strip()

        # Capa 1: substring 5+ palabras
        new_chunks = new_norm.split()
        existing_chunks = existing_norm.split()
        if len(new_chunks) >= 5 and len(existing_chunks) >= 5:
            for i in range(len(new_chunks) - 4):
                chunk = " ".join(new_chunks[i:i+5])
                if chunk in existing_norm:
                    log.warning("DUP substring: '%s' ⊂ '%s'", chunk, existing[:50])
                    return True

        # Capa 2: 3+ sustantivos significativos compartidos = duplicado
        # (era 2, demasiado estricto en canales mismo nicho)
        existing_sig = _significant_words(existing)
        shared_sig = new_sig & existing_sig
        if len(shared_sig) >= 3:
            log.warning("DUP sustantivos (%d compartidos: %s): '%s' ≈ '%s'",
                        len(shared_sig), shared_sig, new_title[:50], existing[:50])
            return True

        # Capa 3: ratio overlap (más estricto)
        if not existing_sig:
            continue
        overlap = len(shared_sig)
        similarity = overlap / min(len(new_sig), len(existing_sig))
        if similarity >= threshold:
            log.warning("DUP overlap (%.0f%%): '%s' ≈ '%s'", similarity * 100, new_title[:50], existing[:50])
            return True

    return False


CHANNEL_TOPICS_MAP = {
    "VidaSana360": "vidasana360.json",
    "SaludLongevidad": "saludlongevidad.json",
    "CatBrothers": "catbrothers.json",
    "EspacioInteligente": "hogarinteligente.json",
    "FinanzasClara": "finanzasclara.json",
    "DarkFiles": "darkfiles.json",
    "DisasterDecode": "disasterdecode.json",
    "MindWired": "mindwired.json",
    "CashCafe": "cashcafe.json",
}

# Canales que comparten nicho — cross-channel dedup
SIBLING_CHANNELS = {
    "VidaSana360": {"name": "SaludLongevidad", "refresh_token_env": "YT_TOKEN_SALUD"},
    "SaludLongevidad": {"name": "VidaSana360", "refresh_token_env": "YT_TOKEN_PRINCIPAL"},
}


def _load_prewritten_topic(channel: dict) -> dict | None:
    """Carga un tema pre-escrito del banco, marcándolo como usado.

    Lee TODOS los archivos topics/<canal>*.json (base, _extra, _3months, etc.)
    y mergea. Permite añadir bancos adicionales sin tocar este código.
    """
    import glob as _glob

    topics_file = CHANNEL_TOPICS_MAP.get(channel["name"])
    if not topics_file:
        return None

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(project_root, "topics", topics_file)

    if not os.path.exists(path):
        return None

    try:
        # Glob: <stem>.json + <stem>_*.json (cualquier sufijo)
        stem = topics_file.replace(".json", "")
        pattern = os.path.join(project_root, "topics", f"{stem}*.json")
        topic_files = sorted(_glob.glob(pattern))
        # Excluir archivos .used.json u otros no-banco
        topic_files = [f for f in topic_files if not f.endswith(".used") and not f.endswith(".used.json")]

        topics = []
        seen_ids = set()
        for tf in topic_files:
            with open(tf) as f:
                batch = json.load(f)
            for t in batch:
                tid = t.get("id")
                if tid is None or tid in seen_ids:
                    continue
                seen_ids.add(tid)
                topics.append(t)

        if not topics:
            return None

        # Cargar IDs ya usados (un único .used file por canal base)
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

    # 2. Fallback: generar con AI + hard dedup (hasta 6 intentos)
    niche_key = NICHE_MAP.get(channel["name"], "salud_bienestar")
    formulas = CONTENT_FORMULAS.get(niche_key, CONTENT_FORMULAS["salud_bienestar"])

    if all_titles:
        avoid_str = "\n".join(f"- {t}" for t in all_titles[-50:])
    else:
        avoid_str = "(sin historial disponible)"

    # Shuffle formulas para no repetir la misma
    shuffled = formulas[:]
    random.shuffle(shuffled)

    for attempt in range(6):
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

    # Si 6 intentos fallan, ABORTAR — NO subir duplicado
    log.error("DEDUP: 6 intentos fallaron. Último topic: %s. Abortando para no duplicar.", data["topic"][:50])
    raise RuntimeError(f"DEDUP failed after 6 attempts. Last topic: {data['topic'][:80]}")


# ── Estilos rotativos para evitar detección de patrón IA ──
_STYLE_ROTATION_ES = [
    {"opener": "abre con dato impactante puro: 'El X% de... / Esto cuesta Y€... / 3 segundos para...'", "voice_pattern": "frases medio-cortas, pausas naturales, 'mira', 'fíjate', 'ojo'", "structure": "dato → contexto → solución → consecuencia → cierre"},
    {"opener": "abre con pregunta directa: '¿Sabías que...? / ¿Por qué...? / ¿Qué pasa si...?'", "voice_pattern": "tono curioso, hilo que invita a quedarse", "structure": "pregunta → respuesta sorprendente → prueba → aplicación → cierre"},
    {"opener": "abre con mito a desmontar: 'Llevas X años haciendo Y mal / Te mintieron sobre...'", "voice_pattern": "tono firme, ligeramente provocador", "structure": "mito → realidad → prueba → cómo hacerlo bien → cierre"},
    {"opener": "abre con anécdota corta: 'En 1986... / Una mujer en Madrid... / Hace 3 días...'", "voice_pattern": "narrativo, casi cuento", "structure": "anécdota → giro → lección → aplicación → cierre"},
    {"opener": "abre con contradicción: 'Esto suena raro pero... / Lo opuesto a lo que crees...'", "voice_pattern": "tono confidente, como secreto", "structure": "contradicción → explicación → evidencia → consecuencia → cierre"},
]

_STYLE_ROTATION_EN = [
    {"opener": "open with raw stat: 'X% of... / This costs Y... / 3 seconds to...'", "voice_pattern": "mid-short sentences, natural pauses, 'look', 'check this'", "structure": "stat → context → solution → consequence → close"},
    {"opener": "open with direct question: 'Did you know...? / Why does...? / What happens if...?'", "voice_pattern": "curious tone, hooks that keep them watching", "structure": "question → surprising answer → proof → application → close"},
    {"opener": "open with myth-busting: 'You've been doing X wrong for years / They lied about...'", "voice_pattern": "firm, slightly provocative", "structure": "myth → reality → proof → correct way → close"},
    {"opener": "open with short anecdote: 'In 1986... / A woman in Ohio... / Three days ago...'", "voice_pattern": "narrative, almost storytelling", "structure": "anecdote → twist → lesson → application → close"},
    {"opener": "open with contradiction: 'Sounds weird but... / Opposite of what you think...'", "voice_pattern": "confident, like sharing a secret", "structure": "contradiction → explanation → evidence → consequence → close"},
]

# Palabras prohibidas (delatan IA)
_AI_BANNED_ES = ["fascinante", "intrigante", "revolucionario", "imprescindible", "explorar", "navegar", "sumergirse", "embarcamos", "descubre el secreto", "no te lo pierdas", "increíble"]
_AI_BANNED_EN = ["fascinating", "intriguing", "revolutionary", "delve", "embark", "explore", "dive into", "unleash", "amazing", "incredible journey", "discover the secret"]


def generate_content(channel: dict, topic_data: dict) -> dict:
    """Genera guión con texto en pantalla, con anti-detección IA por rotación de estilo."""
    lang = channel.get("language", "es")

    # Rotar estilo según hora UTC + ID tema → variabilidad consistente
    rotation_seed = (int(time.time() // 3600) + abs(hash(topic_data.get("topic", "")))) % 5
    style_es = _STYLE_ROTATION_ES[rotation_seed]
    style_en = _STYLE_ROTATION_EN[rotation_seed]
    seg_count = 6 + (rotation_seed % 3)  # 6-8 variable

    if lang == "en":
        banned = ", ".join(_AI_BANNED_EN)
        prompt = f"""Write a YouTube Short script (25-35s) with text on screen + voice narration.
Channel: {channel['name']} | Tone: {channel['tone']} | Created by Vladys (real human creator)
Topic: {topic_data['topic']}
Hook: {topic_data['hook']}
Key facts: {json.dumps(topic_data['key_points'], ensure_ascii=False)}

STYLE THIS VIDEO:
- Opener: {style_en['opener']}
- Voice pattern: {style_en['voice_pattern']}
- Structure: {style_en['structure']}

ANTI-AI-DETECTION RULES (CRITICAL — YouTube penalizes AI-sounding content):
- BANNED words/phrases: {banned}
- Vary sentence length: mix short punchy lines with one longer explanatory line
- Use occasional human filler: "look", "honestly", "by the way", "real quick"
- Personal voice: occasionally hint at creator perspective ("I tested this", "what changed for me", "in my experience") — sparingly, 1-2 times max per video
- NEVER start segments with the same word twice in a row
- NEVER use perfect parallelism (avoid "first... second... third..." stacks)
- Use natural rhythm: contractions (don't, won't, you're), occasional sentence fragments, em-dashes

HARD RULES:
1. {seg_count} segments (vary durations: some 2s, some 4-5s, NEVER all the same)
2. voice line: 8-18 words MAX, short and natural
3. on-screen text: max 20 chars per slide
4. FIRST segment = scroll-stopping hook (use the style opener above)
5. LAST segment = curiosity-driven CTA. Examples:
   - "Tomorrow I'm posting the one mistake that ruins all this. Subscribe"
   - "Wait until you see what works even better — coming tomorrow. Follow"
   NEVER "Follow for more tips" — generic
6. No emojis in overlays
7. Every segment adds NEW concrete info — no repetition
8. Address viewer as "you" naturally
9. Voice text in plain English — NO markdown, NO quotes inside the field

Respond ONLY JSON:
{{
  "title": "Search-optimized title (60 chars max). Include exact keyword users type. 1 emoji at start. Vary format across videos: question, stat-statement, list, contrast, contradiction. NO generic clickbait.",
  "description": "3 lines, natural keywords, conversational tone. Mention what viewer learns. End with subtle channel CTA.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "segments": [
    {{"voice": "natural narration", "text": "SHORT overlay", "duration": 3}},
    ...
  ],
  "video_prompt": "very specific English visual description for Pexels — concrete objects, settings, actions"
}}"""
    else:
        banned = ", ".join(_AI_BANNED_ES)
        prompt = f"""Escribe guión para YouTube Short (25-35s) con texto en pantalla + voz narrada.
Canal: {channel['name']} | Tono: {channel['tone']} | Creador: Vladys (humano real, cocinero & desarrollador)
Tema: {topic_data['topic']}
Gancho: {topic_data['hook']}
Datos clave: {json.dumps(topic_data['key_points'], ensure_ascii=False)}

ESTILO ESTE VIDEO:
- Apertura: {style_es['opener']}
- Patrón de voz: {style_es['voice_pattern']}
- Estructura: {style_es['structure']}

REGLAS ANTI-DETECCIÓN IA (CRÍTICO — YouTube penaliza contenido sonando a IA):
- PALABRAS PROHIBIDAS: {banned}
- Variar longitud frases: mezcla líneas cortas y punzantes con una línea más larga explicativa
- Muletillas humanas ocasionales: "mira", "fíjate", "vamos al lío", "ojo con esto", "te cuento"
- Voz personal: alguna pincelada del creador ("yo lo probé", "lo que a mí me funcionó", "en mi cocina") — máx 1-2 por video
- NUNCA empieces dos segmentos seguidos con la misma palabra
- NUNCA uses paralelismo perfecto ("primero... segundo... tercero...")
- Ritmo natural: contracciones implícitas, fragmentos de frase, guiones largos para énfasis

REGLAS DURAS:
1. {seg_count} segmentos (variar duraciones: algunos 2s, otros 4-5s, NUNCA todos iguales)
2. Voz: 8-18 palabras MÁX por segmento, frases cortas y naturales
3. Texto pantalla: máx 20 chars
4. PRIMER segmento = gancho que para scroll (usa apertura del estilo)
5. ÚLTIMO segmento = CTA con curiosidad, NO "sígueme para más"
6. Sin emojis en el texto pantalla
7. Cada segmento aporta info NUEVA — sin redundancia
8. Háblale de TÚ al espectador
9. Texto voz en español natural — sin markdown, sin comillas dentro

Responde SOLO JSON:
{{
  "title": "Título búsqueda YouTube (60 chars máx). Incluye keyword exacta que alguien escribiría. 1 emoji al inicio. Variar formato entre videos: pregunta, dato-afirmación, lista, contraste, contradicción.",
  "description": "3 líneas, keywords naturales, tono conversacional. Qué aprende el espectador. CTA sutil al canal.",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "segments": [
    {{"voice": "narración natural", "text": "RESUMEN corto", "duration": 3}},
    ...
  ],
  "video_prompt": "descripción visual EN específica para Pexels — objetos concretos, escenarios, acciones"
}}"""

    data = _call_with_fallback(prompt, primary="github", temperature=0.85)
    log.info("Título: %s", data["title"])
    return data
