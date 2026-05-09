#!/usr/bin/env python3
"""
Genera contenido nuevo LF para 8 canales (excluye donvladys).
Anti-AI rules estrictos. Persistente: track progress en /tmp/content_gen_progress.json.
Uso: python3 scripts/generate_content.py [--channel CAT] [--count 30]
"""
import json, os, sys, time, logging, re, argparse, random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

from groq import Groq
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gen")

PROGRESS_FILE = Path("/tmp/content_gen_progress.json")

# Anti-AI banned words (matches main_longform.py rules)
BANNED_EN = ["fascinating","intriguing","revolutionary","delve","embark","explore","dive into","unleash","amazing","incredible journey","discover the secret","unlock","unveil","game-changer","cutting-edge","groundbreaking","testament","tapestry","journey","navigate","leverage","seamlessly","robust","myriad","plethora"]
BANNED_ES = ["fascinante","intrigante","revolucionario","imprescindible","explorar","navegar","sumergirse","embarcamos","descubre el secreto","no te lo pierdas","increíble","desentrañar","desvelar","viaje","tejido","robusto","miríada","plétora","sin precedentes","transformador"]

CHANNELS = {
    "catbrothers": {
        "lang": "en",
        "niche": "Cat documentaries — curiosities, behavior, breeds, science",
        "tone": "Engaging, fascinating, fun. National Geographic style about cats.",
        "topics_pool": [
            "the science of cat purring frequency for healing",
            "why black cats are unlucky myth — origin and truth",
            "how cats see colors — scientific reality",
            "why cats hate water — evolutionary explanation",
            "cat aging in human years — the real conversion",
            "how long cats remember — memory studies",
            "why cats follow you to the bathroom — social science",
            "the strange habit of cats bringing dead prey home",
            "famous cat owners in history",
            "how cats survived the Black Death plague",
            "why cats sit on paper — territorial behavior",
            "the difference between male and female cats",
            "how cats regulate their body temperature",
            "why cats love boxes — science explained",
            "the truth about cat declawing",
            "why cats hiss — communication signals decoded",
            "how cats see motion versus humans",
            "the most expensive cat breeds in the world",
            "why cats fear cucumbers — viral myth debunked",
            "the science of cat napping cycles",
            "how cats predict bad weather",
            "why some cats are aggressive and others docile",
            "the lifespan record holders in cats",
            "how cats helped win wars — military history",
            "why cats stare at walls — possible explanations",
            "the most loyal cat breeds — bonding science",
            "how to tell if your cat is happy — body signals",
            "why cats lick themselves obsessively",
            "the science of cat whiskers detecting air currents",
            "how indoor cats stay healthy long term",
            "why cats love high places",
            "the role of cats in ancient Rome",
            "how cats hunt at night — predator anatomy",
            "why some cats are terrified of strangers",
            "the science of cat dreams",
        ],
    },
    "finanzas_clara": {
        "lang": "en",
        "niche": "Personal finance for US/UK audience — taxes, savings, freelancers",
        "tone": "Practical, data-driven, no fluff. Like Money Guy Show.",
        "topics_pool": [
            "freelancer tax deductions you're missing in the US",
            "2026 IRS changes that affect self-employed workers",
            "how to save 5000 dollars on a low salary",
            "self-employment tax explained for first-year freelancers",
            "tricks to legally pay less income tax",
            "LLC vs sole proprietor — which one saves you more",
            "your rights when the IRS audits you",
            "electronic invoicing rules for US freelancers",
            "quarterly estimated taxes — Form 1040-ES guide",
            "Schedule C vs Schedule SE — what's the difference",
            "tax withholding for independent contractors",
            "vehicle expenses deduction for self-employed",
            "deductible expenses the IRS approves for freelancers",
            "surviving your first year as a freelancer financially",
            "Social Security tax for self-employed in 2026",
            "invoicing international clients — VAT and US tax rules",
            "how to prepare for an IRS audit step by step",
            "real income contributions — pros and traps",
            "family member as business assistant — tax rules",
            "reduce your electric bill by 50 percent in 90 days",
            "weekly grocery shopping for 30 dollars — meal plan",
            "negotiate your fixed bills like a pro",
            "investing 50 dollars a month — index funds guide",
            "best cashback and discount apps in 2026",
            "the 48-hour rule for impulse purchases",
            "build an emergency fund from zero",
            "common errors in your tax return that trigger audits",
            "primary residence tax deductions explained",
            "deductible donations on your tax return",
            "401k vs index funds — where to put your money",
            "lesser known state tax deductions",
            "credit score improvement in 30 days",
            "bank fees you should never pay",
            "freelancer insurance you actually need",
            "how to budget when income is irregular",
        ],
    },
    "salud_longevidad": {
        "lang": "es",
        "niche": "Longevidad, salud cerebral, anti-envejecimiento, hábitos basados en ciencia",
        "tone": "Riguroso, basado en evidencia, accesible. Estilo Peter Attia en español.",
        "topics_pool": [
            "ayuno intermitente y su efecto en la longevidad",
            "los 5 ejercicios que más alargan la vida según ciencia",
            "rapamicina y antienvejecimiento — qué dice la evidencia",
            "el sueño profundo como antídoto del Alzheimer",
            "marcadores biológicos clave para medir tu edad real",
            "polifenoles y por qué deberías comerlos cada día",
            "la conexión intestino-cerebro y la longevidad",
            "Vitamina D — cuánta tomar realmente según estudios",
            "magnesio y los 3 tipos que sí funcionan",
            "ejercicio de fuerza después de los 50 — guía científica",
            "cafeína y longevidad — lo que dicen los datos",
            "el aceite de oliva virgen extra y la mortalidad",
            "los 7 mitos sobre el colesterol que debes desterrar",
            "exposición al sol — cómo dosificarla para vivir más",
            "la dieta mediterránea desmenuzada por la ciencia",
            "frío terapéutico — la ciencia de las duchas frías",
            "saunas y el riesgo cardiovascular — el estudio finlandés",
            "el rol del magnesio en el cerebro envejeciendo",
            "creatina y rendimiento mental — dosis óptima",
            "ácidos grasos omega-3 y demencia",
            "VO2 max — el mejor predictor de mortalidad",
            "qué desayunar realmente para vivir más",
            "los suplementos sin evidencia que tiras tu dinero",
            "la zona azul de Cerdeña — qué hacen distinto",
            "estrés crónico y telómeros — la ciencia",
            "alcohol — la realidad sin maquillaje según meta-análisis",
            "tabaco — cómo reparar pulmones en 10 años",
            "fibra y mortalidad — los gramos exactos al día",
            "música y demencia — la evidencia ignorada",
            "yoga, meditación y longitud de telómeros",
            "los probióticos que realmente funcionan",
            "Vitamina K2 y arterias — el nutriente olvidado",
            "el ejercicio en ayunas — pros y contras reales",
            "soledad — el factor de mortalidad más subestimado",
            "el chequeo médico anual obligatorio a partir de los 40",
        ],
    },
    "cash_cafe": {
        "lang": "en",
        "niche": "Personal money — habits, side hustles, mindset, psychology",
        "tone": "Conversational, motivating but realistic. Coffee chat style.",
        "topics_pool": [
            "the 1 percent better rule for finances",
            "millionaire morning routines actually backed by research",
            "side hustles that pay 100 dollars a day in 2026",
            "the psychology of overspending decoded",
            "how compound interest really works in real life",
            "rich people habits that are actually free",
            "money scripts — the unconscious beliefs ruining your wallet",
            "how to ask for a raise and actually get it",
            "the dollar cost averaging strategy explained simply",
            "why most people stay broke — behavioral economics",
            "how to negotiate any bill in 5 minutes",
            "the FIRE movement — what they don't tell you",
            "passive income myths versus reality",
            "how to invest your first 1000 dollars",
            "the envelope budgeting method in 2026",
            "why lottery winners go broke — what we can learn",
            "the concept of lifestyle inflation explained",
            "credit card rewards — when they hurt you",
            "the savings rate that actually changes your life",
            "remote jobs that pay over 80k without a degree",
            "the Pareto principle for personal finance",
            "what minimalism saves you per year",
            "high-yield savings accounts compared 2026",
            "how to retire 10 years early — real plan",
            "the dangers of buy now pay later schemes",
            "freelance pricing — how to charge what you're worth",
            "the truth about cryptocurrency for beginners",
            "real estate investing for renters",
            "the financial impact of having pets",
            "how to teach kids about money early",
            "the budget that works for irregular income",
            "stoic principles for managing money",
            "why financial literacy is missing in schools",
            "the 24-hour rule for major purchases",
            "the 3 fund portfolio explained",
        ],
    },
    "dark_files": {
        "lang": "en",
        "niche": "True crime, unsolved mysteries, cold cases, real investigations",
        "tone": "Serious, investigative, respectful to victims. Documentary style.",
        "topics_pool": [
            "the Springfield Three disappearance — case files",
            "the Long Island serial killer — what we know now",
            "the Setagaya family murder — Japan's coldest case",
            "the disappearance of Jennifer Kesse",
            "the Boy in the Box mystery — finally identified",
            "the Yuba County Five — frozen wilderness mystery",
            "the disappearance of Maura Murray analyzed",
            "the Connecticut river killings reopened",
            "the Original Night Stalker — golden state killer truth",
            "the disappearance of Madeleine McCann timeline",
            "the Tylenol murders — still unsolved",
            "the West Mesa bone collector",
            "the Babes in the Woods — Stanley Park",
            "Bobby Dunbar — the boy who came home a stranger",
            "the I-5 Strangler explained",
            "the Atlas Vampire of Stockholm",
            "the Sumter County Does identified",
            "the Jamison family disappearance",
            "the Springfield Three new evidence",
            "Asha Degree — Shelby's missing girl",
            "the Beaumont children Australia",
            "the Tamam Shud man identified through DNA",
            "the Servant Girl Annihilator — first US serial killer",
            "the Hammersmith nude murders",
            "the Doodler — San Francisco's unknown killer",
            "the Astrid Kollman case — Vienna mystery",
            "Lars Mittank disappearance Bulgaria",
            "the Toledo torso murders",
            "the Cleveland torso killer",
            "Jack the Stripper — London's forgotten predator",
            "the Hammer of Hanover",
            "the Bloody Benders — pioneer killers",
            "the Texarkana phantom",
            "the Vampire of Sacramento",
            "the Beast of GEvauandan modern theory",
        ],
    },
    "mind_wired": {
        "lang": "en",
        "niche": "Brain science, psychology, behavior, cognition, mental performance",
        "tone": "Curious, accessible, science-rigorous. Style of Andrew Huberman.",
        "topics_pool": [
            "dopamine fasting — what neuroscience really says",
            "why your brain hates you working from home",
            "the neuroscience of falling in love",
            "how trauma rewires the brain — and how it heals",
            "memory palaces — the technique used by champions",
            "the science behind imposter syndrome",
            "how social media changes your brain — fMRI evidence",
            "the placebo effect — even when you know it",
            "lucid dreaming — the neuroscience and how to do it",
            "why you can't stop scrolling — dopamine loops",
            "the dark side of meditation rarely discussed",
            "neuroplasticity after 40 — the latest research",
            "why we procrastinate — fight or flight at the desk",
            "the neuroscience of habits — making and breaking",
            "boredom and creativity — the missing link",
            "the brain on caffeine — dose-response curves",
            "how alcohol shrinks your brain — the studies",
            "the science of intuition — gut feelings explained",
            "why some people never feel anxiety",
            "the difference between sadness and depression neurologically",
            "introvert versus extrovert brains — neuroimaging studies",
            "why we cry — emotional theory of evolution",
            "music and the brain — emotional response decoded",
            "why some songs give us chills — frisson research",
            "the neuroscience of regret",
            "perfect pitch — born or trained",
            "the autistic brain — what we get wrong",
            "ADHD in adults — diagnosis and reality",
            "why we forget faces but remember songs",
            "the science of gut feelings versus logic",
            "synesthesia — when senses cross",
            "deja vu — what causes it",
            "near-death experiences — what neuroscience says",
            "ego death — psychedelics and identity",
            "the default mode network and rumination",
        ],
    },
    "disaster_decode": {
        "lang": "en",
        "niche": "Natural disasters, history, science, survival, geological events",
        "tone": "Educational, dramatic but accurate. National Geographic Disasters style.",
        "topics_pool": [
            "the Cumbre Vieja megatsunami threat",
            "Yellowstone supervolcano — what science actually says",
            "the Tunguska event — Siberia 1908",
            "Lake Nyos disaster — when CO2 killed a village",
            "the Vajont dam disaster — Italy 1963",
            "the Halifax explosion — largest pre-nuclear blast",
            "Krakatoa 1883 — the eruption heard worldwide",
            "the Galveston hurricane — America's deadliest",
            "the Banqiao dam failure — China 1975",
            "the Lisbon earthquake of 1755 — birth of seismology",
            "the Tangshan earthquake 1976 — the death toll truth",
            "the Year Without a Summer — Tambora's aftermath",
            "the New Madrid earthquakes — when the Mississippi flowed backwards",
            "the great smog of London — when air killed",
            "the Boscastle flash flood — Britain's wake-up call",
            "the Ring of Fire — why disasters cluster",
            "the Beirut port explosion analyzed",
            "the Sahel droughts — climate failure",
            "the Pompeii pyroclastic surge — minute by minute",
            "the Camille hurricane — Mississippi 1969",
            "the Holuhraun fissure eruption — Iceland's silent giant",
            "the Bay of Bengal cyclones — South Asia's annual threat",
            "the Wenchuan earthquake response",
            "the Tohoku tsunami's reach across the Pacific",
            "the Cascadia subduction zone — America's hidden risk",
            "the Lake Toba supereruption 75000 years ago",
            "the Black Saturday bushfires — Australia 2009",
            "the Mount St. Helens lateral blast",
            "the Iran earthquake of 2003 — Bam destruction",
            "the Kobe 1995 earthquake — modern disaster lessons",
            "the Chicxulub impact — dinosaur extinction event",
            "the Storegga slide tsunami — Stone Age catastrophe",
            "the Carrington Event — solar storm of 1859",
            "the Aleppo earthquake of 1138",
            "the Indus Valley flood theories",
        ],
    },
    "vidasana360": {
        "lang": "es",
        "niche": "Salud, dieta, bienestar y hábitos saludables basados en evidencia",
        "tone": "Cercano, práctico, riguroso. Estilo divulgador médico amigo.",
        "topics_pool": [
            "qué desayunar para no tener hambre hasta mediodía",
            "los 5 errores más comunes al hacer ayuno intermitente",
            "alimentos que reducen la inflamación crónica",
            "cómo dormir profundo en menos de 10 minutos",
            "el cortisol matutino y por qué amaneces cansado",
            "los 3 minerales que la mayoría tomamos mal",
            "ejercicios de 10 minutos que sí cambian tu cuerpo",
            "café — los mitos y las verdades de la ciencia",
            "agua con limón en ayunas — pseudociencia versus realidad",
            "cómo activar el sistema linfático para desintoxicar",
            "los antinutrientes y cómo neutralizarlos al cocinar",
            "creatina para mujeres mayores de 40 — ciencia",
            "el papel real de la fibra en la salud intestinal",
            "estiramientos antes de dormir para mejorar tu postura",
            "los 7 hábitos que la gente más sana del mundo comparte",
            "respiración 4-7-8 para reducir ansiedad rápido",
            "cómo recuperar tu microbioma tras antibióticos",
            "señales tempranas de prediabetes que ignoramos",
            "el arroz blanco — ¿realmente es tan malo?",
            "ejercicio en ayunas — ventajas y peligros reales",
            "los aceites de cocina que sí debes usar",
            "cómo tu intestino afecta tu estado de ánimo",
            "recuperación muscular natural sin suplementos caros",
            "el frío como herramienta antiinflamatoria",
            "los 5 alimentos prohibidos para tu hígado",
            "el papel de la melatonina más allá del sueño",
            "exposición al sol en invierno — cuánto necesitas",
            "los hábitos que envejecen tu piel sin que lo sepas",
            "cuándo realmente sirve un suplemento multivitamínico",
            "ejercicios para tendinitis sin parar tu rutina",
            "alergias estacionales — alimentos que las empeoran",
            "té verde — por qué la cafeína sienta distinta",
            "edulcorantes artificiales — qué dice la ciencia 2026",
            "magnesio glicinato versus citrato — diferencias",
            "el rol del zinc en la inmunidad y libido",
        ],
    },
    "hogarinteligente": {  # EspacioInteligente
        "lang": "en",
        "niche": "Smart home tech, automation, energy efficiency, IoT, practical guides",
        "tone": "Practical, tech-savvy but accessible. Style of Linus Tech Tips home edition.",
        "topics_pool": [
            "smart thermostat ROI — real numbers from Energy Star",
            "matter protocol — the future of smart home in 2026",
            "best home assistants compared — Alexa vs Google vs Apple",
            "smart blinds — are they worth it economically",
            "the dark side of smart home privacy",
            "starting a smart home in 2026 with 200 dollars",
            "smart leak detectors that pay for themselves",
            "energy monitoring devices — the actual savings",
            "Zigbee versus Z-Wave — choose the right protocol",
            "Home Assistant versus paid alternatives",
            "smart locks — the security risks they don't tell you",
            "smart smoke detectors versus traditional ones",
            "the cost of running a fully smart home in electricity",
            "smart irrigation — saving water in drought areas",
            "Wi-Fi versus Bluetooth Mesh for IoT devices",
            "robot vacuums in 2026 — features that matter",
            "the truth about smart bulb lifespans",
            "smart plugs — the simplest automation upgrade",
            "smart shower heads — saving water effectively",
            "smart garage doors — security flaws to avoid",
            "voice assistant comparison for non-English speakers",
            "smart pet feeders — what works versus marketing",
            "smart air quality monitors that matter",
            "smart bidet toilets — the western adoption curve",
            "kitchen automation — induction and smart ovens",
            "home security cameras without cloud subscription",
            "smart curtains — DIY versus brand",
            "the rise of solar plus battery smart homes",
            "smart fans and humidity control",
            "child-safe smart home setups",
            "elderly-friendly smart home automation",
            "smart sprinklers and weather APIs",
            "indoor garden automation systems",
            "smart bird feeders with cameras",
            "energy storage at home — Tesla Powerwall alternatives",
        ],
    },
}

# AI fallback chain
def _call_groq(prompt, temp=0.85):
    c = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=120.0, max_retries=0)
    r = c.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}],
        response_format={"type":"json_object"},
        temperature=temp, max_tokens=8000,
    )
    return json.loads(r.choices[0].message.content)

def _call_github(prompt, temp=0.85):
    c = OpenAI(base_url="https://models.inference.ai.azure.com",
               api_key=os.getenv("GITHUB_TOKEN"), timeout=180.0, max_retries=0)
    r = c.chat.completions.create(
        model="DeepSeek-V3-0324",
        messages=[{"role":"user","content":prompt}],
        temperature=temp, max_tokens=8000,
    )
    txt = r.choices[0].message.content.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```\w*\n", "", txt)
        txt = re.sub(r"\n```$", "", txt)
    return json.loads(txt)

def _call_nvidia(prompt, temp=0.85):
    c = OpenAI(base_url="https://integrate.api.nvidia.com/v1",
               api_key=os.getenv("NVIDIA_API_KEY"), timeout=180.0, max_retries=0)
    r = c.chat.completions.create(
        model="meta/llama-3.3-70b-instruct",
        messages=[{"role":"user","content":prompt}],
        temperature=temp, max_tokens=8000,
    )
    txt = r.choices[0].message.content.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```\w*\n", "", txt)
        txt = re.sub(r"\n```$", "", txt)
    return json.loads(txt)

def call_ai(prompt, temp=0.85):
    # NVIDIA primary (translator uses Groq), reduce collision with parallel jobs
    providers = [_call_nvidia, _call_github, _call_groq]
    for attempt in range(9):
        fn = providers[attempt % 3]
        try:
            return fn(prompt, temp)
        except Exception as e:
            err = str(e)[:120]
            wait = 60 if "429" in str(e) else 10
            log.warning("Provider %s fail (attempt %d): %s — wait %ds", fn.__name__, attempt+1, err, wait)
            time.sleep(wait)
    raise RuntimeError("All providers failed")


PROMPT_EN = """You are a documentary scriptwriter for YouTube channel "{channel_name}".
Niche: {niche}
Tone: {tone}

WRITE A COMPLETE DOCUMENTARY ABOUT: {topic}

REQUIREMENTS:
- 25 segments minimum
- Each segment: 3-5 narration sentences (50-80 words)
- Total: 1800+ narration words
- ALL facts REAL and VERIFIABLE — cite studies, universities, real sources
- Cite WHERE data comes from (university, study, year)
- Language: in English, accessible, no unnecessary jargon

ANTI-AI-DETECTION (CRITICAL — YouTube penalizes AI patterns):
- BANNED words/phrases: {banned}
- Vary sentence length within segments (mix short punch + longer detail)
- Use natural transitions: "Here's the catch.", "But it's not that simple.", "What changes everything is this:"
- Avoid perfect parallelism (no enumerated stacks)
- Occasional creator-perspective hint ("in my own home", "what I tried") — sparingly, max 2 per script
- NEVER start consecutive segments with the same word
- Use contractions, em-dashes, fragments where natural

STRUCTURE:
1-3: Impactful hook + surprising fact + topic context
4-8: Main development — data, studies, explanations
9-14: Deep dive — real cases, practical examples
15-20: More evidence, contrasts, myths vs reality
21-25: Practical conclusions + strong CTA

LAST SEGMENT: Urgency CTA — "Subscribe and hit the bell. What's coming next week goes deeper."

Respond JSON ONLY:
{{
  "title": "SEO title max 60 chars, 1 relevant emoji",
  "description": "YouTube description 3-4 lines with natural keywords, sources mentioned, channel CTA",
  "tags": ["tag1","tag2",...,"tag10"],
  "segments": [
    {{"voice": "full narration 3-5 sentences with real data", "visual": "B-roll Pexels search query in English", "duration": 25}}
  ],
  "thumbnail_text": "2-3 impactful words"
}}"""

PROMPT_ES = """Eres un guionista de documentales en YouTube para el canal "{channel_name}".
Nicho: {niche}
Tono: {tone}

ESCRIBE UN DOCUMENTAL COMPLETO SOBRE: {topic}

REQUISITOS:
- Mínimo 25 segmentos
- Cada segmento: 3-5 frases de narración (50-80 palabras)
- Total: 1800+ palabras de narración
- Todos los datos REALES y VERIFICABLES — citar estudios, universidades, fuentes reales
- Si mencionas un dato, di DE DÓNDE viene (universidad, estudio, año)
- Idioma: español de España, accesible, sin jerga innecesaria

ANTI-AI-DETECTION (CRÍTICO — YouTube penaliza patrones IA):
- Palabras/frases PROHIBIDAS: {banned}
- Variar longitud de frases dentro de segmentos (mezcla corto + detalle largo)
- Transiciones naturales: "Aquí está el truco.", "Pero no es tan simple.", "Lo que cambia todo es esto:"
- Evitar paralelismos perfectos (no enumeraciones apiladas)
- Hint creator-perspective ocasional ("en mi propia cocina", "lo que yo probé") — escaso, max 2 por guión
- NUNCA empezar segmentos consecutivos con la misma palabra
- Usar contracciones, guiones largos, fragmentos donde sea natural

ESTRUCTURA:
1-3: Hook impactante + dato sorprendente + contexto
4-8: Desarrollo principal — datos, estudios, explicaciones
9-14: Profundización — casos reales, ejemplos
15-20: Más evidencia, contrastes, mitos vs realidad
21-25: Conclusiones prácticas + CTA fuerte

ÚLTIMO SEGMENTO: CTA con urgencia — "Suscríbete y dale a la campana. Lo que viene la próxima semana va más profundo."

Responde JSON ÚNICAMENTE:
{{
  "title": "título SEO max 60 chars, 1 emoji relevante",
  "description": "descripción YouTube 3-4 líneas con keywords naturales, fuentes mencionadas, CTA del canal",
  "tags": ["tag1","tag2",...,"tag10"],
  "segments": [
    {{"voice": "narración completa 3-5 frases con datos reales", "visual": "búsqueda Pexels en inglés", "duration": 25}}
  ],
  "thumbnail_text": "2-3 palabras impactantes"
}}"""


def load_progress():
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {}

def save_progress(p):
    PROGRESS_FILE.write_text(json.dumps(p, indent=2))


def next_index(folder):
    """Find next free script number in folder."""
    base = Path(__file__).parent / folder
    base.mkdir(exist_ok=True)
    nums = []
    for f in base.glob("*.json"):
        m = re.match(r"^(\d+)_", f.name)
        if m: nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


def slugify(text, maxlen=40):
    s = re.sub(r"[^\w\s-]", "", text.lower())
    s = re.sub(r"[\s-]+", "_", s).strip("_")
    return s[:maxlen]


def generate_one(channel_key, topic):
    cfg = CHANNELS[channel_key]
    banned = ", ".join(BANNED_EN if cfg["lang"] == "en" else BANNED_ES)
    prompt_t = PROMPT_EN if cfg["lang"] == "en" else PROMPT_ES
    prompt = prompt_t.format(
        channel_name=channel_key, niche=cfg["niche"],
        tone=cfg["tone"], topic=topic, banned=banned,
    )
    for attempt in range(3):
        try:
            data = call_ai(prompt, temp=0.85 + 0.05*attempt)
            segs = data.get("segments", [])
            words = sum(len(s.get("voice","").split()) for s in segs)
            if len(segs) >= 20 and words >= 1300:
                return data
            log.warning("Short script attempt %d: %d segs %d words", attempt+1, len(segs), words)
        except Exception as e:
            log.warning("Gen attempt %d fail: %s", attempt+1, str(e)[:120])
            time.sleep(15)
    raise RuntimeError("Failed after 3 attempts")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", help="Single channel (default: all)")
    ap.add_argument("--count", type=int, default=30, help="Scripts per channel")
    args = ap.parse_args()

    progress = load_progress()
    channels = [args.channel] if args.channel else list(CHANNELS.keys())

    for ch in channels:
        if ch not in CHANNELS:
            log.warning("Unknown channel %s, skip", ch); continue
        cfg = CHANNELS[ch]
        used_topics = set(progress.get(ch, {}).get("used_topics", []))
        pool = [t for t in cfg["topics_pool"] if t not in used_topics]
        log.info("=== %s: %d topics in pool, target %d new scripts ===", ch, len(pool), args.count)

        produced = 0
        for topic in pool:
            if produced >= args.count: break
            try:
                log.info("[%s] %d/%d generating: %s", ch, produced+1, args.count, topic[:60])
                script = generate_one(ch, topic)
                idx = next_index(ch)
                slug = slugify(script.get("title", topic))
                fname = f"{idx:02d}_{slug}.json"
                path = Path(__file__).parent / ch / fname
                path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
                log.info("[%s] saved %s", ch, fname)

                progress.setdefault(ch, {}).setdefault("used_topics", []).append(topic)
                progress[ch]["produced"] = progress[ch].get("produced", 0) + 1
                save_progress(progress)
                produced += 1
                time.sleep(45)
            except Exception as e:
                log.error("FAIL %s/%s: %s", ch, topic[:40], str(e)[:120])
                time.sleep(60)

        log.info("--- %s done: %d new ---", ch, produced)

    log.info("ALL CHANNELS COMPLETE")


if __name__ == "__main__":
    main()
