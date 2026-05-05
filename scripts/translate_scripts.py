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
    providers = [_call_groq, _call_github]
    for attempt in range(6):  # 6 total attempts cycling providers
        fn = providers[attempt % len(providers)]
        try:
            result = fn(prompt)
            return result
        except Exception as e:
            err = str(e)
            wait = 30 if "429" in err else 10
            log.warning("Provider failed (attempt %d): %s — waiting %ds", attempt+1, err[:80], wait)
            time.sleep(wait)
    raise RuntimeError("All providers failed after 6 attempts")


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


def translate_file(path: Path, finance_mode: bool = False) -> bool:
    """Returns True if translated, False if skipped (already English)."""
    data = json.loads(path.read_text(encoding="utf-8"))

    # Skip if already in English (check title)
    title = data.get("title", "")
    if not any(ord(c) > 127 for c in title) and len(title) > 5:
        # Check a segment voice line
        first_voice = data.get("segments", [{}])[0].get("voice", "")
        spanish_words = ["que", "los", "las", "del", "con", "por", "para", "una", "este"]
        if not any(w in first_voice.lower().split() for w in spanish_words):
            log.info("SKIP (already English): %s", path.name)
            return False

    prompt_template = PROMPT_FINANCE_ADAPT if finance_mode else PROMPT_DIRECT
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

    DIRS = {
        "catbrothers": False,       # direct translation
        "salud_longevidad": False,   # direct translation
        "finanzas_clara": True,      # finance adaptation
    }

    total = 0
    translated = 0
    failed = 0

    for folder, finance_mode in DIRS.items():
        script_dir = base / folder
        files = sorted(script_dir.glob("*.json"))
        log.info("=== %s: %d files ===", folder, len(files))

        for i, f in enumerate(files):
            total += 1
            try:
                done = translate_file(f, finance_mode=finance_mode)
                if done:
                    translated += 1
                # Rate limit: pause between calls (scripts are large, need longer wait)
                if i < len(files) - 1:
                    time.sleep(30)
            except Exception as e:
                log.error("FAILED %s: %s", f.name, str(e)[:120])
                failed += 1
                time.sleep(10)

        log.info("--- %s done ---", folder)

    log.info("COMPLETE: %d total, %d translated, %d failed", total, translated, failed)


if __name__ == "__main__":
    main()
