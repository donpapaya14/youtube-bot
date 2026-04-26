"""
Descarga clips de video de Pexels como fallback cuando Veo 2 no está disponible.
"""

import logging
import os
import requests

log = logging.getLogger(__name__)

API_URL = "https://api.pexels.com/videos/search"


def download_clips(search_terms: list[str], output_dir: str, num_clips: int = 4) -> list[str]:
    """Busca y descarga clips verticales de Pexels. Devuelve lista de paths."""
    api_key = os.getenv("PEXELS_API_KEY")
    headers = {"Authorization": api_key}
    paths = []
    seen_ids = set()

    for term in search_terms:
        if len(paths) >= num_clips:
            break

        try:
            resp = requests.get(
                API_URL,
                headers=headers,
                params={
                    "query": term,
                    "per_page": 5,
                    "orientation": "portrait",
                    "size": "medium",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            for video in data.get("video_files", []) if "video_files" in data else []:
                # Pexels devuelve videos en data["videos"]
                pass

            for video_item in data.get("videos", []):
                if len(paths) >= num_clips:
                    break
                if video_item["id"] in seen_ids:
                    continue
                seen_ids.add(video_item["id"])

                # Buscar archivo HD en formato vertical
                best_file = _pick_best_file(video_item.get("video_files", []))
                if not best_file:
                    continue

                path = os.path.join(output_dir, f"pexels_{video_item['id']}.mp4")
                _download_file(best_file["link"], path)
                paths.append(path)
                log.info("Descargado: %s (%s)", path, term)

        except Exception as e:
            log.warning("Error buscando '%s' en Pexels: %s", term, e)

    if not paths:
        log.error("No se pudo descargar ningún clip de Pexels")

    return paths


def _pick_best_file(files: list[dict]) -> dict | None:
    """Elige el mejor archivo de video: preferir HD, vertical."""
    # Preferir archivos con altura > ancho (vertical) y buena calidad
    candidates = []
    for f in files:
        w = f.get("width", 0)
        h = f.get("height", 0)
        if h >= w and h >= 720:
            candidates.append(f)

    if not candidates:
        # Si no hay vertical, tomar cualquiera con buena resolución
        candidates = [f for f in files if f.get("height", 0) >= 720]

    if not candidates:
        candidates = files

    if not candidates:
        return None

    # Preferir HD (1080) pero no 4K (demasiado pesado)
    candidates.sort(key=lambda f: abs(f.get("height", 0) - 1080))
    return candidates[0]


def _download_file(url: str, path: str):
    """Descarga archivo con streaming."""
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
