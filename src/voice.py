"""
Generación de voz con Edge TTS (Microsoft).
Gratis, sin API key, voces naturales en español.
"""

import asyncio
import logging
import os

import edge_tts

log = logging.getLogger(__name__)

# Voces españolas de alta calidad
VOICES = {
    "male": "es-ES-AlvaroNeural",
    "female": "es-ES-ElviraNeural",
    "male_mx": "es-MX-JorgeNeural",
    "female_mx": "es-MX-DaliaNeural",
}


def generate_voice_segments(segments: list[dict], output_dir: str, voice: str = "male") -> list[dict]:
    """Genera audio para cada segmento. Devuelve segments con path y duración real."""
    voice_id = VOICES.get(voice, VOICES["male"])
    results = []

    for i, seg in enumerate(segments):
        text = seg["voice"]
        audio_path = os.path.join(output_dir, f"voice_{i}.mp3")

        try:
            asyncio.run(_generate_audio(text, voice_id, audio_path))

            # Obtener duración real del audio
            duration = _get_duration(audio_path)

            results.append({
                "voice": text,
                "text": seg.get("text", ""),
                "audio_path": audio_path,
                "duration": max(duration, 2.0),  # Mínimo 2 segundos
            })
            log.info("Voz %d: %.1fs - %s", i, duration, text[:50])

        except Exception as e:
            log.warning("Error TTS segmento %d: %s", i, e)
            # Fallback: usar duración del segmento original
            results.append({
                "voice": text,
                "text": seg.get("text", ""),
                "audio_path": None,
                "duration": seg.get("duration", 3),
            })

    return results


async def _generate_audio(text: str, voice: str, output: str):
    """Genera audio con Edge TTS."""
    communicate = edge_tts.Communicate(text, voice, rate="+10%")
    await communicate.save(output)


def _get_duration(audio_path: str) -> float:
    """Obtiene duración de un archivo de audio con ffprobe."""
    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True, timeout=10,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, AttributeError):
        return 3.0
