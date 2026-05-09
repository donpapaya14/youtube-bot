#!/usr/bin/env python3
"""
Traduce bancos de guiones LF de español a inglés.
catbrothers + salud_longevidad → traducción directa
finanzas_clara → adaptación a US/UK personal finance
"""
import json
import os
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("translate")

# ── AI client (reuse from research.py) ──────────────────────────────────────
from groq import Groq
from openai import OpenAI
import re as _re

def _parse_json(text):
    text = text.strip()
    if "<think>" in text:
        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())

def _call_groq(prompt):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"), timeout=90.0, max_retries=0)
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    return json.loads(r.choices[0].message.content)

def _call_github(prompt):
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=os.getenv("GITHUB_TOKEN"),
        timeout=120.0, max_retries=0,
    )
    r = client.chat.completions.create(
        model="DeepSeek-V3-0324",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=4096,
    )
    return _parse_json(r.choices[0].message.content)

def _call_nvidia(prompt):
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY"),
        timeout=90.0, max_retries=0,
    )
    r = client.chat.completions.create(
        model="meta/llama-3.3-70b-instruct",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=4096,
    )
    return _parse_json(r.choices[0].message.content)

def call_ai(prompt):
    providers = [_call_groq, _call_nvidia, _call_github]
    for attempt in range(9):
        fn = providers[attempt % len(providers)]
        try:
            result = fn(prompt)
            return result
        except Exception as e:
            err = str(e)
            wait = 60 if "429" in err else 10
            log.warning("Provider %s failed (attempt %d): %s — waiting %ds", fn.__name__, attempt+1, err[:80], wait)
            time.sleep(wait)
    raise RuntimeError("All providers failed after 9 attempts")


# ── Translation prompts ──────────────────────────────────────────────────────

PROMPT_DIRECT = """Translate this YouTube video script from Spanish to English.
Keep the same structure, facts, scientific references, and tone.
Do NOT change names of studies, researchers, or institutions.
Adapt cultural references naturally for an English-speaking audience.
Keep all durations exactly as-is.
The "visual" field stays as English (it already describes visuals).

Input JSON:
{script}

Return ONLY the translated JSON with the EXACT same structure:
{{
  "title": "translated title",
  "description": "translated description",
  "tags": ["english", "tags"],
  "segments": [
    {{"voice": "translated narration", "visual": "same visual description", "duration": same_number}},
    ...
  ],
  "thumbnail_text": "TRANSLATED TEXT"
}}"""

PROMPT_REVERSE_TO_ES = """Translate this YouTube video script from English to Spanish (Spain).
Keep the same structure, facts, scientific references, and tone.
Do NOT change names of studies, researchers, or institutions.
Use natural Spanish from Spain (not Latin American).
Keep all durations exactly as-is.
The "visual" field stays as English (it already describes visuals for stock footage search).

Input JSON:
{script}

Return ONLY the translated JSON with the EXACT same structure:
{{
  "title": "título traducido en español",
  "description": "descripción traducida",
  "tags": ["etiquetas", "en", "español"],
  "segments": [
    {{"voice": "narración traducida al español", "visual": "same visual description in English", "duration": same_number}},
    ...
  ],
  "thumbnail_text": "TEXTO ES"
}}"""

PROMPT_FINANCE_ADAPT = """Adapt this YouTube video script from Spanish personal finance (Spain-specific) to English personal finance for a US/UK audience.

ADAPTATION RULES:
- autónomo/autónomos → freelancer/self-employed
- Hacienda → IRS (US) or HMRC (UK) — use "tax authority" if ambiguous
- IRPF → income tax
- IVA → VAT (UK) or sales tax (US)
- Modelo 303, Modelo 130 → quarterly tax return
- euros → dollars (keep same numbers)
- Spanish law articles → replace with "according to tax law" or equivalent US/UK rule
- Zona franca, RETA → equivalent US/UK concepts (self-employment tax, Schedule C, etc.)
- Keep the same practical, data-driven tone and structure
- Keep all durations exactly as-is
- The "visual" field stays English (visual descriptions for footage search)

Input JSON:
{script}

Return ONLY the adapted JSON with the EXACT same structure:
{{
  "title": "English title for US/UK audience",
  "description": "English description",
  "tags": ["english", "finance", "tags"],
  "segments": [
    {{"voice": "adapted narration in English", "visual": "same visual description", "duration": same_number}},
    ...
  ],
  "thumbnail_text": "ENGLISH TEXT"
}}"""


_ES_FUNC = {"que","los","las","del","con","para","una","este","como","porque","pero","más","están","años","muy","cuando","ese","esta","tu","si","es","ya","no","me","te","se","en","la","el","de","y","a","por","sus","todo","sin","sobre"}

def _detect_lang(text: str) -> str:
    import re as _r
    words = _r.findall(r"\b\w+\b", text.lower())[:200]
    es_hits = sum(1 for w in words if w in _ES_FUNC)
    return "es" if es_hits >= 5 else "en"


def translate_file(path: Path, mode: str = "es_to_en") -> bool:
    """Returns True if translated, False if skipped (already in target lang).
    mode: 'es_to_en' (direct), 'es_to_en_finance' (US/UK adapt), 'en_to_es' (reverse)."""
    data = json.loads(path.read_text(encoding="utf-8"))

    first_voice = " ".join(s.get("voice","")[:300] for s in data.get("segments",[])[:2])
    actual = _detect_lang(first_voice)
    target = "en" if mode in ("es_to_en", "es_to_en_finance") else "es"

    if actual == target:
        log.info("SKIP (already %s): %s", target, path.name)
        return False

    if mode == "es_to_en_finance":
        prompt_template = PROMPT_FINANCE_ADAPT
    elif mode == "en_to_es":
        prompt_template = PROMPT_REVERSE_TO_ES
    else:
        prompt_template = PROMPT_DIRECT
    prompt = prompt_template.replace("{script}", json.dumps(data, ensure_ascii=False))

    result = call_ai(prompt)

    # Validate structure
    if "segments" not in result or "title" not in result:
        raise ValueError(f"Invalid result structure: {list(result.keys())}")
    if len(result["segments"]) < len(data["segments"]) * 0.8:
        raise ValueError(f"Too few segments: {len(result['segments'])} vs {len(data['segments'])}")

    # Preserve durations from original (AI sometimes changes them)
    orig_segs = data["segments"]
    for i, seg in enumerate(result["segments"]):
        if i < len(orig_segs):
            seg["duration"] = orig_segs[i].get("duration", seg.get("duration", 25))

    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("✓ %s → %s", path.name, result["title"][:60])
    return True


def main():
    base = Path(__file__).parent

    # mode per folder: es_to_en | es_to_en_finance | en_to_es
    DIRS = {
        "catbrothers": "es_to_en",
        "finanzas_clara": "es_to_en_finance",
        "salud_longevidad": "en_to_es",
    }

    total = 0
    translated = 0
    failed = 0

    for folder, mode in DIRS.items():
        script_dir = base / folder
        files = sorted(script_dir.glob("*.json"))
        log.info("=== %s (%s): %d files ===", folder, mode, len(files))

        for i, f in enumerate(files):
            total += 1
            try:
                done = translate_file(f, mode=mode)
                if done:
                    translated += 1
                if i < len(files) - 1:
                    time.sleep(20)
            except Exception as e:
                log.error("FAILED %s: %s", f.name, str(e)[:120])
                failed += 1
                time.sleep(10)

        log.info("--- %s done ---", folder)

    log.info("COMPLETE: %d total, %d translated, %d failed", total, translated, failed)


if __name__ == "__main__":
    main()
