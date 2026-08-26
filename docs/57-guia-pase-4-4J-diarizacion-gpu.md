# Guía del pase 4.4-J — la separación de voces en la GPU de Runpod

**Fecha:** 2026-08-26 · **Base:** `main` en `2531842` · **Especificación:** `docs/56` (operador). **Orden de David:** «desarrolla la diarización para ejecutarse sobre la GPU de Runpod, además de cualquier otro proceso susceptible de dar mejores resultados o ser más rápido».

## Para David, en cinco líneas

La transcripción ya corre en tu GPU (el operador la migró: `large-v3`, 2-4 min). Faltaba el oído: separar las voces, que en la CPU del VPS tarda 34 minutos y otros 33 si repite. Este pase construye el trabajador que hace eso en tu GPU en segundos, con la repetición incluida en el mismo viaje, y deja **todas las decisiones en el VPS** (qué voz es fantasma, cuál de las dos pasadas se queda). Si la GPU no responde, la CPU sigue exactamente como hoy. Un vídeo de 23 min: ~1-2 céntimos de $ de tu saldo prepago. Y de propina, en la GPU se puede probar el sucesor de pyannote (`community-1`) sin tocar la matriz del VPS: es la última carta acústica contra el 95,7/4,3 del post 5.

## Inventario (docs/56 §1): qué pasa por GPU tras este pase

| Etapa | Dónde | Estado |
|---|---|---|
| Transcripción whisper | GPU (`istt-whisper`, operador) | hecho |
| **Diarización + 2ª pasada** | **GPU (`istt-diarize`, este pase)** | **hecho** |
| Cruce, frases, backchannels, fantasmas | VPS (ms) | no gana con GPU |
| Embeddings wiki | VPS (ms) | no gana con GPU (medido por el operador) |
| Pasada de sentido, barrido, veredictos, moderación | API de Claude | no es GPU |
| Descarga | VPS (red) | no es cómputo |

No queda nada más que gane con GPU. Si más adelante se activa el OCR de rótulos (K3, hoy apagado), sería candidato.

## Las piezas

**`workers/gpu/diarize/`** — imagen propia (no existe una pública de confianza):
- `Dockerfile`: base `runpod/pytorch` (CUDA), ffmpeg, pyannote 3.x con torch moderno (**la matriz torch 2.2.2 del VPS no se toca: es de la otra imagen**). Pesos **precargados en el build** (`--build-arg HF_TOKEN=…`); el token **no queda** en la imagen. Intenta precargar también `community-1`; si no está disponible, sigue con 3.1.
- `handler.py`: contrato de docs/56 §4.2. Recibe opus base64, pista y `second_pass_num_speakers`; decodifica a 16 kHz mono; devuelve `turns`, `turns_second_pass` y tiempos. Procesa en un directorio temporal y muere: **no persiste audio ni embeddings** (línea roja de biometría).

**VPS**:
- `gpu._run_job` (lanzar + sondear + cancelar por timeout, compartido con whisper) y `gpu.diarize_gpu(audio, hint, second_pass_n)`.
- `tasks.diarize_turns(post, audio, pista)`: GPU primero si `RUNPOD_DIARIZE_ENDPOINT` está; **siempre que hay duda pide la segunda pasada** (docs/56 §5: segundos); absorbe fantasmas y elige con `keep_better_split`. Sin GPU o con fallo: CPU como hoy (segunda pasada solo con desequilibrio, porque ahí cuesta 30 min).
- Settings: `RUNPOD_DIARIZE_ENDPOINT`, `DIARIZE_GPU_MODEL` (default 3.1). El espejo (MOCK) nunca llama.

## Cómo se publica la imagen (decisión pendiente de David, docs/56 §7)

Dos vías; **elige una**:
1. **Runpod construye desde GitHub**: David conecta GitHub en la consola de Runpod; el endpoint apunta a `workers/gpu/diarize/` del repo; `HF_TOKEN` como build arg y como variable de entorno del template.
2. **El operador construye en el VPS** y la sube a un registry (Docker Hub o GHCR, cuenta de David): `docker build --build-arg HF_TOKEN=… -t <registry>/istt-diarize:4.4-J workers/gpu/diarize && docker push …`; el endpoint usa esa imagen.

La imagen pesa varios GB (CUDA + pesos): la vía 1 evita subirla desde el VPS.

## Validación (el operador): el post 5, en segundos de voz

1. Endpoint creado, `RUNPOD_DIARIZE_ENDPOINT` en el `.env`, Regla de Oro.
2. Llave inglesa → Transcripción y voces → confirmar. Registro esperado: `GPU (diarización, pyannote/speaker-diarization-3.1): N turnos, 2 voces + segunda pasada` y `minoritaria 1ª pasada X% · 2ª pasada Y% → se queda la …`; `diarize_seconds` de segundos, no de miles.
3. Comando de medida en segundos (`docs/49`). Número a batir: 95,7/4,3.
4. Cambiar `DIARIZE_GPU_MODEL=pyannote/speaker-diarization-community-1`, Regla de Oro, repetir y comparar. **Si community-1 separa mejor, pasa a ser el default** (una línea en `settings.py` y `.env.example`).

## Dinero y límites (docs/56 §6, sin cambios)
`workersMin=0`, `idleTimeout≤5`, jamás un Pod persistente. El gasto de Runpod no entra en `DailyBudget` (otro bolsillo, prepago). Nada se persiste en Runpod.
