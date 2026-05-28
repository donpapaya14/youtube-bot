# Mascota CatBrothers — personaje GATO

Genera el personaje (gratis: HF Space PhotoMaker/InstantID, Bing Image Creator, Google ImageFX) y guarda PNG **transparente** aquí:

- `pose_thumb.png`  ← MÍNIMO necesario (el sistema reusa esta si faltan las demás)
- `pose_point.png`, `pose_wave.png`, `pose_think.png`  ← opcionales (dan variedad)

**Prompt sugerido:**
```
Flat vector cartoon mascot of a cute friendly cat, big expressive eyes,
orange accent (#FF9800), bold clean outlines, full body, centered,
plain white background, consistent character.
POSE: <waving hello / pointing to the side / thumbs up / curious head tilt>
```

1. Genera 1-4 imágenes (una por pose).
2. Quita el fondo → PNG transparente (gratis: Photopea, o `rembg`).
3. Suelta aquí con los nombres de arriba.
4. **Prueba antes de que el cron lo suba:** `python src/main.py --channel catbrothers --no-upload`

> ⚠️ CatBrothers vive del LONG-FORM, y la mascota ahora solo va en shorts.
> Para que el gato salga en los LF hay que extender `src/assembler_longform.py` (tarea aparte).
