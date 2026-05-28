# Mascota CashCafe — personaje CAFÉ

(El contenido del canal es de café — el personaje debe ser de café.)

**Prompt sugerido:**
```
Flat vector cartoon mascot, friendly coffee cup character with arms and face
(or a smiling barista), warm orange accent (#FF6B35), bold clean outlines,
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
4. Prueba: `python src/main.py --channel cash_cafe_shorts --no-upload`
