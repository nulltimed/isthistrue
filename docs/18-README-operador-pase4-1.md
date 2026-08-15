# README OPERADOR — Pase 4.1 ejecutado (2026-08-15)

> Este pase NO llegó como ZIP: la orden de trabajo (pase-4.1-orden-de-trabajo.md) encargó el
> desarrollo al propio operador. Este documento es la entrega exigida: causa raíz de B1,
> exclusión de hfcache, matriz del fallback sin JS de B3 y notas de datos.

## B1 — Diarización: causa raíz exacta y arreglo

**Causa raíz (dos capas, ambas confirmadas en build):**
1. `pyannote.audio` 3.x referencia `torchaudio.AudioMetaData`, retirada del torchaudio
   moderno → `AttributeError` al importar (lo confirmó el diagnóstico de David en producción).
2. Al fijar la pareja compatible torch/torchaudio 2.2.2, apareció la segunda capa: torch 2.2.2
   está compilado contra **NumPy 1.x** y pip resolvía NumPy 2.5 → crash de import. (La cazó el
   nuevo candado de build, no producción: exactamente para eso se puso.)

**Matriz de versiones FIJADA (no subir sueltas — cambiar las 4 a la vez y validar):**
`torch==2.2.2+cpu` · `torchaudio==2.2.2+cpu` · `numpy==1.26.4` · `pyannote.audio==3.1.1`
— wheels **CPU-only** (`--extra-index-url download.pytorch.org/whl/cpu`): el VPS no tiene GPU
y la imagen adelgaza cientos de MB de CUDA inútil.

**Candado de build**: `RUN python -c "import pyannote.audio"` en el Dockerfile — una regresión
futura de versiones rompe el BUILD, nunca producción en silencio.

**El except mudo** (`apps/agents/diarization.py`) sustituido por degradación ruidosa:
- sin `HF_TOKEN` → `WARNING «Diarización omitida: HF_TOKEN ausente en .env»`
- cualquier fallo de import/carga/ejecución → `WARNING «Diarización omitida: <excepción exacta>»`
(Regla 5.7; segunda reincidencia tras Turnstile — patrón vigilado.)

**Sin huellas de voz**: nada nuevo persiste; etiquetas genéricas SPEAKER_XX por vídeo,
cero embeddings, cero comparación entre vídeos (§4.7 congelado, intacto).

## Exclusión de hfcache del backup (regla 5.17, vía exclusión justificada)

Volumen nuevo `hfcache` (→ `HF_HOME=/hfcache` en el worker): caché de los modelos pyannote
(cientos de MB, primer arranque). **Excluido del backup a propósito**: es contenido
re-descargable de HuggingFace con el token; copiarlo solo engordaría el depósito cifrado.
Si se pierde, el primer análisis lo re-descarga. En staging: `hfcache_staging` (mock: no se usa).

## B2 — deno

`deno 2.1.4` (binario oficial x86_64, versión fijada por ARG) en la imagen; `deno --version`
como verificación de build. Motivo: sin motor JS, YouTube estrangula a yt-dlp (34 KiB/s
observados en un análisis real → 6+ min para 12 MB).

## B3 — PayPal opción B: matriz del fallback

| Escenario | Qué ve el usuario |
|---|---|
| JS activo | Selector 5 € / 10 € / Otra cantidad (input numérico, coma o punto, mín. 1 €) + botón PayPal oficial `intent=capture&currency=EUR`; `createOrder` con la cantidad elegida; sin ventana en blanco previa |
| JS activo, cantidad inválida | El botón rechaza el click (`actions.reject()`) y el campo muestra «Cantidad mínima: 1 €» via validez nativa del navegador |
| **Sin JS** | `<noscript>`: enlace directo al `paypal_url` de SystemSetting (la cantidad se elige en PayPal); si el setting está vacío, enlace a /donaciones/. El banner nunca queda muerto |
| Registro fiscal | Manual en /panel/donaciones/ (vigente); el servidor ahora RECHAZA importes ≤ 0 o basura |

Suscripción retirada al 100%: `grep -rn 'P-3K755405C1414303ENJZZBAI\|createSubscription'` → vacío
(regla 5.3 cumplida). cookies.html actualizado (el SDK ya no es de suscripción).
**PENDIENTE DAVID**: cancelar el plan de suscripción también en el panel de PayPal (si alguien
se suscribió, las renovaciones seguirían); y rellenar `paypal_url` en /panel/settings/ si aún
está vacío, para que el fallback sin JS tenga destino.

## B4 — Admin con la piel de la web

`templates/admin/base_site.html` (override limpio de Django, cero forks) + `static/css/admin-skin.css`:
logo v4 según idioma, subtítulo administración/administration, «← Volver a la web», favicons ×3,
paleta de la web vía variables CSS del admin, fuentes del sistema (cero Google Fonts), login con
la tarjeta centrada de las páginas auth. Funcionalidad y permisos: INTACTOS.

## Datos y seeds

Sin migraciones. Sin cambios de seeds → sin UPDATEs manuales en BDs existentes en este pase.

## Nota de coordinación

El pase 4.0 (referrer, relegación manual, caja transcripción, clic-para-saltar, Opina,
logout/login) NO ha llegado a este operador: el 4.1 se aplicó solo, sobre main, como permite
la orden. Cuando llegue el 4.0, atención al roce compartido en base.html (invariantes 5.12:
favicon ×3, banner XL —ahora con el selector de cantidad—, selector de idioma).
