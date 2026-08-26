# Encargo para Fable — pase 4.4-J · todas las etapas pesadas a la GPU de Runpod

**De:** Claude Code (operador) · **Para:** Fable (IA de desarrollo)
**Fecha:** 2026-08-26 · **Producción:** `afdc233` (4.4-I desplegado; `RUNPOD_API_KEY` activa)
**Orden de David, literal:** *«Ajusta el modelo de diarización de voz para que sea estricto y
use todos los recursos necesarios de la GPU de Runpod. Lo mismo para el resto de etapas de la
web»* — con autorización permanente para todo lo que acelere o mejore los análisis.

## 0. Estado ya operativo (no lo repitas)

- Cuenta Runpod de David: **prepago, 50 USD de saldo** (verificado por API desde el worker).
- `RUNPOD_API_KEY` en el `.env` de producción y leída por `settings.RUNPOD_API_KEY` (`7eb0871`).
- Conector MCP de Runpod enlazado a su cuenta de Claude (gestión desde el chat).
- El operador crea el endpoint y pone `RUNPOD_ENDPOINT_ID` en el `.env`; **tu trabajo es el
  código cliente y el worker**.

## 1. Arquitectura pedida: serverless, con retorno a CPU

**Endpoint SERVERLESS** (factura solo por segundo de proceso; sin Pods encendidos — condición
del operador). Worker propio en un subdirectorio del repo (p. ej. `workers/gpu/`) con su propio
`Dockerfile` CUDA — **la imagen del VPS no se toca**: la matriz `torch==2.2.2+cpu` fijada en el
4.1 sigue intacta; la imagen GPU es otra, corre en Runpod, y puede llevar torch CUDA moderno.
Runpod construye imágenes desde GitHub (integración nativa): sin registry propio.

**Contrato del handler** (una llamada por vídeo):
```
entrada:  {"audio_url": <URL firmada o descarga directa>, "hint": {num_speakers|min|max},
           "whisper_model": "large-v3", "language": null}
salida:   {"segments": [{start, end, text, words[]}], "turns": [[start, end, label]],
           "tiempos": {"transcribe_s": x, "diarize_s": y}}
```

**Retorno a CPU obligatorio (regla 5.7)**: sin clave, sin endpoint, o con fallo/timeout del
endpoint → la fase barata corre en CPU exactamente como hoy, con `WARNING`. La GPU acelera;
jamás se convierte en punto único de fallo.

## 2. «Estricto»: la subida de calidad que la GPU hace pagable

| Etapa | Hoy (CPU) | Con GPU (lo pedido) |
|---|---|---|
| Transcripción | faster-whisper **small-int8** | **large-v3**, `word_timestamps=True`, `beam_size=5` |
| Separación de voces | pyannote 3.1, 34 min/vídeo | pyannote 3.1 (o **community-1**, §45: pruébalo aquí — la imagen GPU no está atada a la matriz del VPS) en 1-3 min |
| 2ª pasada (`keep_better_split`) | 33 min extra — dolorosa | **segundos** — puede incluso probarse N=2 y N=3 y elegir |
| Pasada de sentido / veredictos | Claude (sin cambio) | Claude (sin cambio — esto no va a GPU) |

`small` → `large-v3` es el mayor salto de calidad disponible: menos palabras inventadas, mejor
puntuación y reloj por palabra más fino — que alimenta directamente el cruce de voces. En CPU
era impagable (horas); en GPU son ~2-4 min por vídeo de 23.

## 3. Coste (para el panel y para David)

GPU clase RTX 4090/A5000 serverless ≈ 0,60-0,90 $/h facturada por segundo. Vídeo de 23 min con
large-v3 + diarización + 2ª pasada ≈ **3-6 min de GPU ≈ 0,04-0,08 $**. Los 50 $ de saldo dan
para **600-1.000 vídeos**. El gasto sale del saldo prepago de Runpod (techo natural), NO de
`DailyBudget` — pero muéstralo informativamente donde ya se muestran los costes.

## 4. Líneas rojas aplicadas a la GPU

- **Biometría**: igual que hoy — el worker GPU procesa y DEVUELVE etiquetas por vídeo; no
  persiste embeddings de voz ni audio (el contenedor serverless muere tras cada trabajo).
- El audio que se envía es el de vídeos públicos ya procesados hoy; nada de datos de usuarios.
- `RUNPOD_API_KEY`/`RUNPOD_ENDPOINT_ID` solo en `.env`; jamás en el repo ni en logs.
- Datacenter UE si el template lo permite (preferencia, no bloqueo).

## 5. Reparto del trabajo

**Tuyo (el pase 4.4-J)**: `workers/gpu/` (Dockerfile CUDA + handler), cliente en `tasks.py`
(descarga → llamada al endpoint con reintentos → retorno a CPU), `whisper_model` y ajustes
estrictos, tests con `httpx` doblado, y el cronómetro distinguiendo GPU/CPU (`analysis_times`).
**Del operador**: crear el endpoint (API/MCP), poner `RUNPOD_ENDPOINT_ID` en los `.env`,
desplegar y medir contra el post 5 — la comparativa small-CPU vs large-v3-GPU saldrá en el
informe del pase.

**Prioridad**: es EL pase siguiente. La cola de veredictos, el panel y las voces ya están; esto
multiplica la capacidad de la plataforma (~52 min → <10 por vídeo) y sube la calidad de raíz.
