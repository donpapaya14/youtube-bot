# Spec — Sistema de mascota por canal (VidaSana360)

**Fecha:** 2026-05-28
**Estado:** aprobado (diseño) → implementación
**Contexto estratégico:** ver `/Users/vladys/Proyectos/ANALISIS-IMPERIO-CONTENIDO-2026-05-28.md`. La mascota da identidad → sube CTR → combate la supresión de contenido faceless (problema #1). Se despliega SOLO en el canal ganador (VidaSana360), no en canales muertos.

## Objetivo
Añadir una mascota (caricatura de Vladys) reutilizable al pipeline de shorts, en 3 puntos: thumbnail, marca de agua en vídeo y tarjeta outro con CTA. Cero coste recurrente (solo FFmpeg/PIL ya usados). Cero APIs de pago.

## Decisiones de diseño
- **Concepto:** caricatura cartoon de Vladys (conecta con DonVladys, refuerza "creador humano real").
- **Aparece en:** thumbnail (esquina inf-dcha) + marca de agua persistente (esquina) + tarjeta outro 1.5s ("Suscríbete"). **Sin intro** (protege retención de shorts).
- **Estilo:** flat cartoon / vector.
- **Poses:** 4 → `wave`, `point`, `thumb`, `think`.
- **Generación del arte:** manual, 1 vez, gratis (ComfyUI+InstantID local o Bing/ImageFX). Se entrega prompt al usuario. La implementación arranca con **placeholders PIL** para validar el pipeline hoy.

## Arquitectura (aislada, fallback-safe)
```
assets/mascots/vidasana360/        PNGs transparentes: pose_wave.png, pose_point.png, pose_thumb.png, pose_think.png
src/mascot.py            (nuevo)   resolución de assets + config por canal
src/gen_placeholder_mascot.py (nuevo, util) genera placeholders PIL (se borra al tener arte real)
src/assembler.py         (editado) 3 enganches: thumbnail, watermark, outro
channels/vida_sana_360.json (editado) bloque "mascot"
```

### Unidades
- **`src/mascot.py`**
  - `get_mascot(channel, pose="thumb") -> str | None` — path al PNG de la pose pedida; cae a otras poses; `None` si no hay arte o `mascot.enabled` es falso.
  - `mascot_config(channel) -> dict` — bloque config con defaults (scale, posición, outro).
  - Contrato: NUNCA lanza. Sin arte → `None`. Consumidores tratan `None` como "sin mascota".
- **`assembler.py` enganches** (todos condicionados a `get_mascot(...) is not None`, con `try/except` → fallback a comportamiento actual):
  1. `generate_shorts_thumbnail`: `Image.paste(mascota, (x,y), mascota)` (alpha) antes de guardar. Pose `thumb`.
  2. `_compose_final`: 1 input PNG extra + 1 overlay `overlay=X:Y` persistente (marca de agua, pose `point`/`wave`). Índices de input calculados con contador explícito.
  3. Outro: tarjeta PNG (mascota pose `wave` + texto "Suscríbete") generada estilo `_render_slide`, overlay con `enable='between(t, dur-1.5, dur)'`.

### Config (`channels/vida_sana_360.json`)
```json
"mascot": {
  "enabled": true,
  "dir": "assets/mascots/vidasana360",
  "scale": 0.22,
  "watermark_pos": "bottom-right",
  "watermark_pose": "point",
  "outro": true,
  "outro_text": "Suscríbete 👇"
}
```

## Flujo de datos
`main.run() → assemble_video(channel, ...)` → lee `channel["mascot"]`. Si `enabled` + hay arte → compone con mascota (thumbnail + watermark + outro). Si no → pipeline actual intacto, bit a bit.

## Manejo de errores
- Mascota es **aditiva, nunca bloqueante**. Cada enganche en `try/except`; ante fallo → log warning + continúa sin mascota.
- Falta carpeta/PNG → `get_mascot` devuelve `None` → se omite el overlay.
- FFmpeg: si el filtro con mascota falla, NO hay reintento sin mascota automático en v1 (se valida en test local antes de activar en cron). Riesgo mitigado por test.

## Testing / verificación
- Generar placeholders → renderizar 1 short de prueba de VidaSana360 en local (`python src/main.py --channel vida_sana_360`, o harness de prueba) → verificar por inspección: thumbnail con mascota, watermark visible en vídeo, tarjeta outro al final. **No subir a YouTube** (test local).
- Confirmar fallback: con `mascot.enabled=false` el output es idéntico al actual.

## Fuera de alcance (v1)
- Mascota que habla (Wav2Lip/SadTalker) → fase posterior.
- Despliegue a otros canales → tras validar CTR/retención en VidaSana360.
- Generación automática del arte → manual por ahora.

## Lo que hace el usuario
Generar su caricatura en 4 poses (prompt entregado) → soltar PNGs transparentes en `assets/mascots/vidasana360/`. El sistema los coge automáticamente y sustituye los placeholders.
