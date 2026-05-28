# Mascota CatBrothers — personaje GATO

Genera el personaje (gratis: HF Space, Bing Image Creator, Google ImageFX) y guarda PNG **transparente** aquí.

**Prompt sugerido:**
```
Flat vector cartoon mascot of a cute friendly cat, big expressive eyes,
orange accent (#FF9800), bold clean outlines, full body, centered,
plain white background, consistent character.
POSE: <waving / pointing / thumbs up / curious>
```

## Estática (mínimo)
- `pose_thumb.png`  ← MÍNIMO (se reusa en thumbnail/marca de agua/outro si faltan las demás)
- `pose_point.png`, `pose_wave.png`, `pose_think.png`  ← opcionales (variedad)

## Para que HABLE (mouth-swap, opcional)
Dos versiones **idénticas** del personaje, **mismo tamaño y posición**, que solo cambian la boca:
- `pose_talk_closed.png`  ← boca cerrada
- `pose_talk_open.png`    ← boca abierta
Truco: genera 1, duplícala y edita la boca abierta (Photopea, gratis). Si ambas existen → el muñeco mueve la boca con la voz automáticamente. Si no → marca de agua estática.

## Pasos
1. Genera. 2. Quita fondo → PNG transparente (Photopea / `rembg`). 3. Suelta aquí.
4. Prueba antes de subir: `python src/main.py --channel catbrothers --no-upload`

> ⚠️ CatBrothers vive del LONG-FORM, y la mascota ahora solo va en shorts.
> Para que el gato salga en los LF hay que extender `src/assembler_longform.py` (tarea aparte).
