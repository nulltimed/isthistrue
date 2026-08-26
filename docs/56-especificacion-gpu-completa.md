# Especificación completa — TODO el análisis acelerable, por la GPU de Runpod

**De:** Claude Code (operador) · **Para:** Fable (IA de desarrollo, "Claude web")
**Fecha:** 2026-08-26 · **Producción:** `f0bff08` · **Sustituye y amplía:** `docs/54`
**Orden de David que ejecuta este documento:** *«todo lo necesario para que todas las tareas
susceptibles de dar mejores y más rápidos resultados se ejecuten por GPU»*, bajo su
autorización permanente (gasto del saldo prepago de Runpod incluido, hoy 50 USD).

---

## 1. Inventario COMPLETO del pipeline: qué va a GPU y qué no

Etapa por etapa, con el criterio aplicado (¿la GPU da mejor resultado, más rápido, o ambos?):

| # | Etapa | Hoy | ¿GPU? | Veredicto |
|---|---|---|---|---|
| 1 | Descarga yt-dlp | CPU (I/O) | — | **No**: limitada por red, no por cómputo |
| 2 | **Transcripción whisper** | ✅ **YA EN GPU** (`large-v3`, operador, `d9cc3c6`) | ✅ | **Hecho** — ver §3 |
| 3 | **Diarización pyannote** | CPU, 34 min/vídeo | ✅✅ | **TU PIEZA CENTRAL** — ver §4 |
| 4 | 2ª pasada de voces (`keep_better_split`) | CPU, +33 min | ✅✅ | Misma pieza que #3: en GPU son segundos — ver §5 |
| 5 | Cruce palabras↔voces, frases, backchannels | CPU, milisegundos | — | **No**: Python puro, instantáneo |
| 6 | Embeddings wiki (MiniLM 384d local) | CPU, ~ms por claim | — | **No, evaluado hoy**: el viaje de red costaría más que el cómputo |
| 7 | Pasada de sentido / barrido / clasificador / datación / veredictos / moderación | API de Claude | — | **No es trabajo de GPU** (es de modelos de lenguaje por API) |
| 8 | OCR de rótulos | desactivado (K3, decisión de David) | — | No aplica |

**Conclusión ejecutiva**: con la transcripción ya migrada, **queda UNA pieza: el worker GPU de
diarización (+2ª pasada)**. Es tu pase 4.4-J. Todo lo demás o ya está, o no gana con GPU.

## 2. Lo que ya existe y NO debes rehacer

- **Endpoint** `istt-whisper` (`mxqg9olrlfglni`), imagen oficial `runpod/ai-api-faster-whisper:1.0.10`,
  GPU `NVIDIA RTX A5000` (0,27 $/h) → respaldo `RTX 4090` (0,74 $/h), `workersMin=0`, `idleTimeout=5`.
- **Cliente** `apps/agents/gpu.py`: opus mono 24k → base64 (tope 9,5 MB de `/run`), `/run` +
  sondeo `/status`, **cancelación remota si vence `RUNPOD_JOB_TIMEOUT`** (900 s), y regla 5.7:
  todo fallo → `None` → CPU como siempre. 5 tests en `OperadorGPUWhisper`.
- **Settings**: `RUNPOD_API_KEY`, `RUNPOD_WHISPER_ENDPOINT`, `WHISPER_GPU_MODEL=large-v3`,
  `RUNPOD_JOB_TIMEOUT`, `RUNPOD_POLL_SECONDS`. Solo en `.env` de producción (espejo = MOCK, sin GPU).
- **Trampa de contrato medida contra el hierro** (la doc oficial no lo cuenta): con
  `word_timestamps=True`, las palabras llegan en `output.word_timestamps` (lista GLOBAL
  `{word,start,end}`), NO dentro de `segments`. `_map_output` las reparte por reloj con puntero.
- **Trampa de la API REST de Runpod**: `POST /v1/templates` sin `isServerless: true` crea una
  plantilla de Pod y el endpoint la RECHAZA («cannot use pod templates»). Borrar y recrear.

## 3. Contrato del worker de whisper (por si necesitas tocarlo)

```
POST https://api.runpod.ai/v2/<EP>/run   Authorization: Bearer <RUNPOD_API_KEY>
{"input": {"audio_base64": <opus/ogg b64>, "model": "large-v3",
           "word_timestamps": true, "beam_size": 5}}
→ {"id": <job>}   ·   GET /status/<job> → {"status": "IN_QUEUE|IN_PROGRESS|COMPLETED|FAILED",
   "executionTime": ms, "output": {"segments": [...], "word_timestamps": [...],
   "detected_language": "en", "device": "cuda", "model": "large-v3"}}
POST /cancel/<job> — SIEMPRE al abandonar por timeout (dinero).
```

## 4. TU PIEZA: el worker GPU de diarización (pase 4.4-J)

No existe imagen pública de confianza con pyannote serverless: se construye propia, en el repo.

### 4.1 Estructura pedida

```
workers/gpu/diarize/
├── Dockerfile          # base runpod/pytorch (CUDA); torch MODERNO aqui — la matriz
│                       # torch==2.2.2+cpu del VPS NO se toca (es de la otra imagen)
├── handler.py          # runpod.serverless.start({"handler": ...})
└── requirements.txt    # pyannote.audio (3.1 Y community-1 seleccionable), runpod
```

### 4.2 Contrato del handler (simétrico al de whisper)

```
entrada: {"audio_base64": <opus b64>,                  # mismos limites que §3
          "hint": {"num_speakers": N} | {"min_speakers": a, "max_speakers": b} | {},
          "model": "pyannote/speaker-diarization-3.1" | "pyannote/speaker-diarization-community-1",
          "second_pass_num_speakers": N | null}        # si viene, hace TAMBIEN la 2ª pasada
salida:  {"turns": [[start, end, "SPEAKER_00"], ...],
          "turns_second_pass": [...] | null,           # el VPS elige con keep_better_split
          "tiempos": {"diarize_s": x, "second_pass_s": y}}
```

**Clave de diseño**: la 2ª pasada se hace EN EL MISMO TRABAJO (el audio ya está en la GPU;
evita otro viaje de 5 MB y otro arranque). El VPS sigue decidiendo con `keep_better_split` —
la política se queda en nuestro código, el músculo en la GPU (lección 4.4-E: el candado en
el código).

### 4.3 Detalles que te ahorran errores

- `HF_TOKEN` va como **variable de entorno del template** del endpoint (lo pongo yo al
  crearlo), no en cada petición.
- El handler recibe opus: decodifica con torchaudio/ffmpeg a 16 kHz mono antes de pyannote.
- **community-1**: pruébalo AQUÍ (imagen GPU, sin el corsé de la matriz del VPS). El dato del
  §45 (95,7/4,3 con las dos voces del post 5) es el caso de prueba: si community-1 lo separa
  mejor, es el modelo por defecto. Expón `model` en la entrada para poder comparar por panel.
- Cold start: la imagen debe PRECARGAR los pesos en el build (RUN python -c "Pipeline.from_pretrained(...)")
  con el token de build — si los baja en el arranque, cada trabajo frío paga 1-2 min.
- Vídeos cuyo opus no quepa en 9,5 MB de base64 (≈ >45 min): en esta fase, retorno a CPU
  (como whisper). La mejora limpia — que el worker descargue el audio él mismo con yt-dlp —
  es una decisión de diseño tuya; si la tomas, cuidado: las URLs de googlevideo van atadas a
  IP, tendría que descargar del ORIGEN (URL del post), no de una URL firmada por el VPS.

### 4.4 El lado VPS (tu código en `apps/`)

- `diarize_gpu(audio_path, hint, second_pass_n)` en `apps/agents/gpu.py`, calcado al patrón
  de `transcribe_gpu` (mismo sondeo, misma cancelación, mismo `None` → CPU).
- En `run_cheap_phase`: GPU primero si `RUNPOD_DIARIZE_ENDPOINT` está; si devuelve `None`,
  pyannote local EXACTAMENTE como hoy. El flujo de capas del 4.4-I no cambia: solo cambia
  DÓNDE corre el oído.
- Settings nuevos: `RUNPOD_DIARIZE_ENDPOINT`, `DIARIZE_GPU_MODEL` (default 3.1 hasta que
  community-1 demuestre en el caso del §45).
- Tests: los cinco de `OperadorGPUWhisper` como plantilla + uno que verifique que
  `turns_second_pass` pasa por `keep_better_split` (la política NO se delega a la GPU).

## 5. Lo que la GPU HABILITA además de acelerar (inclúyelo en el pase)

- La 2ª pasada deja de ser un lujo de 33 min: **siempre que haya duda, se pide** (el
  `second_pass_num_speakers` del contrato). Coste marginal: segundos.
- El suelo de calidad `min_identified_speakers_percent` (65) puede subirse si la GPU +
  large-v3 mejoran el cruce — mídelo antes, no lo subas a ciegas.
- Transcripción y diarización pueden ir **EN PARALELO** (hoy van en serie): son dos endpoints
  independientes con el mismo audio. La fase barata queda en ~max(2-4, 1-3) min + Claude.
  Hazlo solo si no complica el manejo de errores: en serie ya es 10 veces más rápido que hoy.

## 6. Dinero, límites y líneas rojas (sin cambios, aplicadas a GPU)

- Saldo prepago = techo. Coste esperado por vídeo de 23 min: **3-6 céntimos de $** (whisper
  2-4 + diarización 1-2). Los 50 $ ≈ **800-1.600 análisis completos**.
- `workersMin=0` SIEMPRE. Jamás un Pod persistente. `idleTimeout` ≤ 5.
- **Biometría**: el worker procesa y muere; PROHIBIDO persistir embeddings de voz o audio en
  Runpod (volúmenes, caches de red, S3). Las etiquetas por vídeo son lo único que vuelve.
- El gasto Runpod NO entra en `DailyBudget` (es otro bolsillo, prepago); muéstralo
  informativamente donde el panel ya enseña costes. Los paneles de dinero siguen siendo de David.
- El espejo NUNCA llama a la GPU (`MOCK_AGENTS=true` ya lo corta: mantenlo así).

## 7. Reparto y ritual

**Tuyo**: `workers/gpu/diarize/` + `diarize_gpu` + integración + tests + guía de operador.
**Del operador**: crear el endpoint de diarización (§2 tiene las trampas de la API), poner
`RUNPOD_DIARIZE_ENDPOINT` y el `HF_TOKEN` del template, desplegar con el ritual completo y
**medir contra el post 5** (§45: 95,7/4,3 es el número a batir; segundos de voz, no frases).
**El operador construye y publica la imagen si tu pase la define**: Runpod puede construir
desde GitHub (requiere que David conecte GitHub en su consola de Runpod — pídelo en tu README
de operador si eliges esa vía) o yo la construyo en el VPS y la subo a un registry si David
crea cuenta en Docker Hub/GHCR — dilo explícitamente en la guía del pase.

## 8. Estado de verificación al escribir esto

- Whisper GPU: probado 2 veces contra el endpoint real (large-v3, cuda, Gettysburg OK).
- Integración VPS: CI 295/295; espejo OK; producción entra al terminar el análisis en vuelo.
- Diarización GPU: **sin empezar** — este documento es su especificación completa.
