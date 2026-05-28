# Mascota EspacioInteligente — personaje HOGAR

**Prompt sugerido** (robot-ayudante de hogar, o persona con spray de limpieza):
```
Flat vector cartoon mascot, friendly little home-helper robot (or a cheerful
person holding a cleaning spray), blue accent (#1976D2), bold clean outlines,
full body, centered, plain white background, consistent character.
POSE: <waving / pointing / thumbs up / thinking>
```

## Estática (mínimo)
- `pose_thumb.png`  ← MÍNIMO (se reusa si faltan las demás)
- `pose_point.png`, `pose_wave.png`, `pose_think.png`  ← opcionales

## Para que HABLE (mouth-swap, opcional)
Dos versiones idénticas, mismo tamaño/posición, solo cambia la boca:
- `pose_talk_closed.png` (boca cerrada) + `pose_talk_open.png` (boca abierta)
Si ambas existen → mueve la boca con la voz. Si no → estática.

## Pasos
1. Genera. 2. Quita fondo → PNG transparente (Photopea / `rembg`). 3. Suelta aquí.
4. Prueba: `python src/main.py --channel hogarinteligente --no-upload`
