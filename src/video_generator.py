"""
Generación de video con Veo 2 vía Gemini API.
OPCIONAL: solo funciona si GEMINI_API_KEY tiene quota disponible.
Si no está disponible, devuelve lista vacía → main.py usa Pexels.
"""

import logging
import os
import time

log = logging.getLogger(__name__)


def generate_video(prompt: str, output_dir: str, num_clips: int = 4) -> list[str]:
    """Intenta generar clips de video con Veo 2. Devuelve lista de paths o lista vacía."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        log.info("GEMINI_API_KEY no configurada. Usando Pexels.")
        return []

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except ImportError:
        log.info("google-genai no instalado. Usando Pexels.")
        return []

    paths = []
    for i in range(num_clips):
        try:
            log.info("Generando clip %d/%d con Veo 2...", i + 1, num_clips)
            operation = client.models.generate_videos(
                model="veo-2.0-generate-001",
                prompt=prompt,
                config={
                    "number_of_videos": 1,
                    "duration_seconds": 8,
                    "aspect_ratio": "9:16",
                },
            )

            timeout = 300
            elapsed = 0
            while not operation.done and elapsed < timeout:
                time.sleep(15)
                elapsed += 15
                operation = client.operations.get(operation)

            if not operation.done:
                log.warning("Timeout generando clip %d", i + 1)
                continue

            for j, video in enumerate(operation.result.generated_videos):
                path = os.path.join(output_dir, f"veo_clip_{i}_{j}.mp4")
                video.video.save(path)
                paths.append(path)
                log.info("Clip guardado: %s", path)

        except Exception as e:
            log.info("Veo 2 no disponible: %s. Usando Pexels.", e)
            return []

    return paths
