# Mascota EspacioInteligente — personaje HOGAR

Genera el personaje (gratis: HF Space, Bing Image Creator, Google ImageFX) y guarda PNG **transparente** aquí:

- `pose_thumb.png`  ← MÍNIMO necesario (el sistema reusa esta si faltan las demás)
- `pose_point.png`, `pose_wave.png`, `pose_think.png`  ← opcionales

**Prompt sugerido** (robot-ayudante de hogar, o mano amiga con tema casa):
```
Flat vector cartoon mascot, friendly little home-helper robot (or a cheerful
person holding a cleaning spray), blue accent (#1976D2), bold clean outlines,
full body, centered, plain white background, consistent character.
POSE: <waving hello / pointing to the side / thumbs up / thinking>
```

1. Genera 1-4 imágenes. 2. Quita el fondo → PNG transparente (Photopea / `rembg`).
3. Suelta aquí. 4. Prueba: `python src/main.py --channel hogarinteligente --no-upload`
