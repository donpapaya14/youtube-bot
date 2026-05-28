"""
Resolución de assets de mascota por canal.

Aditivo y fallback-safe: si no hay arte o la mascota está desactivada,
todas las funciones devuelven None y el pipeline sigue sin mascota.

Estructura esperada de assets:
    assets/mascots/<canal>/pose_wave.png
    assets/mascots/<canal>/pose_point.png
    assets/mascots/<canal>/pose_thumb.png
    assets/mascots/<canal>/pose_think.png
(PNGs con transparencia)

Config en channels/<canal>.json:
    "mascot": {"enabled": true, "dir": "assets/mascots/vidasana360", ...}
"""

import logging
import os

log = logging.getLogger("mascot")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSES = ["wave", "point", "thumb", "think"]


def _resolve_dir(cfg: dict | None) -> str | None:
    """Devuelve el directorio de assets si la mascota está activa y existe."""
    if not cfg or not cfg.get("enabled"):
        return None
    d = cfg.get("dir") or ""
    if not d:
        return None
    path = d if os.path.isabs(d) else os.path.join(_PROJECT_ROOT, d)
    return path if os.path.isdir(path) else None


def get_mascot(cfg: dict | None, pose: str = "thumb") -> str | None:
    """cfg = bloque 'mascot' del canal. Devuelve path al PNG de la pose o None.

    Cae a otras poses si la pedida no existe; None si no hay ningún PNG.
    Nunca lanza.
    """
    try:
        d = _resolve_dir(cfg)
        if not d:
            return None
        order = [f"pose_{pose}.png"] + [f"pose_{p}.png" for p in POSES if p != pose]
        for name in order:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
        pngs = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
        return os.path.join(d, pngs[0]) if pngs else None
    except Exception as e:
        log.warning("get_mascot: %s", str(e)[:100])
        return None


def from_channel(channel: dict | None, pose: str = "thumb") -> str | None:
    """Helper: extrae el bloque 'mascot' del canal y resuelve la pose."""
    return get_mascot((channel or {}).get("mascot"), pose)


def get_exact(cfg: dict | None, pose: str) -> str | None:
    """Como get_mascot pero SIN fallback: devuelve el path solo si pose_<pose>.png existe.

    Usado para las poses de boca (talk_closed/talk_open): si no están ambas,
    no se activa la animación (cae a marca de agua estática).
    """
    try:
        d = _resolve_dir(cfg)
        if not d:
            return None
        p = os.path.join(d, f"pose_{pose}.png")
        return p if os.path.exists(p) else None
    except Exception:
        return None
