# Mascota CashCafe — personaje CAFÉ

(El contenido del canal es de café — el personaje debe ser de café, no de dinero.)

Genera el personaje (gratis: HF Space, Bing Image Creator, Google ImageFX) y guarda PNG **transparente** aquí:

- `pose_thumb.png`  ← MÍNIMO necesario (el sistema reusa esta si faltan las demás)
- `pose_point.png`, `pose_wave.png`, `pose_think.png`  ← opcionales

**Prompt sugerido:**
```
Flat vector cartoon mascot, friendly coffee cup character with arms and face
(or a smiling barista), warm orange accent (#FF6B35), bold clean outlines,
full body, centered, plain white background, consistent character.
POSE: <waving hello / pointing to the side / thumbs up / thinking>
```

1. Genera 1-4 imágenes. 2. Quita el fondo → PNG transparente (Photopea / `rembg`).
3. Suelta aquí. 4. Prueba: `python src/main.py --channel cash_cafe_shorts --no-upload`
