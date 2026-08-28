# Informe del pase 4.4-J — La separación de voces en tu GPU (y la cacería que costó)

**Fecha:** 2026-08-26 · **Operador:** Claude Code · **Commits:** `e9acf70` (pase) + 7 fixes del operador hasta `05d9ce1`
**CI:** verde en todos (303 → 304 tests) · **Producción:** actualizada · **Espejo:** aprobado en cada paso

---

## 1. El resultado, primero

**El análisis completo del post 5 (22,8 min de vídeo) por el circuito GPU:**

| | Ayer (CPU) | **Hoy (GPU)** | Mejora |
|---|---|---|---|
| Separación de voces (con 2ª pasada) | 66 min | **3 min** | **22×** |
| Transcripción | 16,6 min (`small`) | 25 min* (`large-v3`) | mejor modelo |
| **Fase barata completa** | **83 min** | **29 min** | **2,9×** |
| Coste GPU | — | **~7 céntimos** | |

*La transcripción incluye la descarga del vídeo (~12 min, el cuello real ahora) y el modelo
se carga por trabajo en la imagen oficial de whisper — mejorable, apuntado abajo.

**Y la mecánica nueva, funcionando a la vista:** la segunda pasada de voces vino en el mismo
viaje GPU y `keep_better_split` eligió **la mejor** (minoritaria 5,9 % → 8,6 %, se quedó la
2ª): la corrección del 4.4-I actuando en la dirección buena por primera vez.

## 2. La cacería: siete trampas entre el parche y el primer análisis real

El pase de Fable era correcto — **el handler funcionó a la primera en local**. Todo lo demás
fue plataforma, y cada trampa quedó cerrada con su candado:

1. **`huggingface_hub` 1.x** eliminó `use_auth_token` → precarga de pesos muerta. *Fix: pin <1.0.*
2. **El fallback tolerante cacheaba el fallo** de `community-1` (David aún no había aceptado
   las condiciones) → los rebuilds reutilizaban el intento fallido para siempre. *Fix: rompe-caché.*
3. **pyannote 4 en tres diferencias de contrato**: exige torch ≥2.8 (imagen aparte), lee audio
   vía `torchcodec` (roto en los workers) y devuelve `DiarizeOutput` sin `itertracks`.
   *Fixes: imagen slim con base runtime 2.8; el audio entra como tensor PCM crudo (vale para
   pyannote 3 y 4); la salida se desenvuelve por atributos.*
4. **Los pools de GPU de Runpod mienten**: «AMPERE_24» servía particiones MIG de Blackwell
   (¡y el filtro de versiones CUDA tampoco lo impidió!). *Mitigación: pool AMPERE_48 (A40
   reales) + imagen compatible con toda arquitectura.*
5. **La imagen -devel pesaba 21 GB** y un centro de datos con enlace flojo al registro de
   GitHub tardaba >1 h en bajarla. *Fix: imagen slim de 8,7 GB (base runtime).*
6. 🏆 **EL CUELGUE SILENCIOSO** — el jefe final. En CUALQUIER worker (Blackwell y A40 por
   igual), la carga del pipeline se quedaba eterna sin un solo mensaje; en el VPS, 2,5 s.
   Instrumenté el handler con `faulthandler` (volcado de pilas cada 120 s) y el propio proceso
   colgado confesó la línea: **`numpy.linalg.inv` en el setup PLDA** — OpenBLAS en hosts de
   ~128 núcleos despliega hilos que el cgroup del contenedor no concede y gira para siempre.
   *Fix: `OMP_NUM_THREADS=4` y hermanas, horneadas en las tres imágenes. El faulthandler se
   queda: el próximo cuelgue de cualquier causa se delatará solo.*
7. **`attribution_note` (varchar 160) no cupo** la razón de Haiku con el contexto rico de
   large-v3 → un `DataError` tumbó la pasada de sentido entera del primer análisis GPU.
   *Fix: truncado leído del límite real del campo + test (304).*

Reglas de plataforma que quedan para siempre: **un release nuevo NO recicla al worker
caliente** (la palanca real es `workersMax` 0→1); **no matar a un worker que inicializa**
(pierde la descarga); tope de ejecución de 15 min en el endpoint (ningún cuelgue puede
facturar más que céntimos).

## 3. Coste total del día

Depuración GPU completa: **~35-40 céntimos** de los 50 $ (dos cuelgues facturados antes del
tope, el análisis real de 7 céntimos y una docena de pruebas de céntimo). El saldo prepago
hizo exactamente su papel de techo.

## 4. Calidad: donde estamos y qué falta

El primer análisis GPU quedó en 93,3/6,0 con 5 inciertas — **sin la capa de comprensión**
(la mató la trampa 7; sus cambios parciales sí quedaron aplicados). La comparación limpia
con el mejor resultado histórico (88,6/11,3, ayer con sense pass completa) llegará con el
próximo análisis, ya con todo el circuito sano. Y queda una bala nueva: **`community-1` sobre
el vídeo completo** — la medición está corriendo mientras escribo esto; resultado en `docs/06`.

## 5. Pendientes que hereda Fable (docs/06 §50)

- El modelo de whisper se carga POR TRABAJO en la imagen oficial (~40 s/análisis): un worker
  propio con modelo residente lo eliminaría. Decisión de coste para David.
- La descarga del vídeo (~12 min) es ahora el cuello de la fase barata: que el worker GPU
  descargue él mismo es la mejora natural (cuidado: URLs de googlevideo atadas a IP).
- `DIARIZE_GPU_MODEL` es conmutables por `.env`; si la medición de community-1 gana, el
  cambio de default es una línea.

---

## 6. Aclaraciones de David (2026-08-27) — respondidas y vigentes

**«¿Tengo que cambiar algo en el `.env`?»** No: el operador ya puso
`DIARIZE_GPU_MODEL=pyannote/speaker-diarization-community-1` en el `.env` de producción
(autorización de calidad), y es la configuración que produjo el 67,3/32,7. Pendiente solo de
Fable: fijar ese valor como default de fábrica en `settings.py` para que el `.env` no tenga
que decirlo.

**«¿`OMP_NUM_THREADS=4` significa que pyannote no aprovecha toda la GPU?»** No — esa variable
limita **hilos de CPU**, no la GPU. Afecta únicamente a un cálculo auxiliar de numpy (la
inversión de matriz del setup PLDA, una vez, al cargar el modelo), que sin el límite se
quedaba colgado para siempre en los hosts de ~128 núcleos ANTES de llegar a usar la GPU. La
separación de voces corre entera en los núcleos CUDA sin ninguna restricción: 22 s el vídeo
completo (vs 33-66 min en CPU). Cinturón del vestíbulo; el motor va a tope.

**«¿Se usa pyannote 3 o 4? Quiero la más moderna.»** Se usa la más moderna en todo el camino
real: la imagen activa (`4.4-J-slim`) lleva **pyannote.audio 4.0.7** ejecutando
**community-1** (el modelo más nuevo de la familia). pyannote 3 solo queda en el retorno a
CPU del VPS — la red de seguridad que únicamente actúa si la GPU no responde, y que es
deliberadamente la matriz vieja y estable de la máquina de producción.
