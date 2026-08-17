# Mapa de todo lo implementado — isthistrue. / escierto.

**Fecha:** 2026-08-17 · **Commit:** `114a305` · **Autor:** Claude Code (operador)
**Qué es esto:** el inventario completo de lo que la plataforma **hace hoy**, sacado del
código y de la base de datos reales, no de los informes. Los 27 informes de `docs/` cuentan
cada pase por separado; este documento cuenta **el resultado acumulado**.
**Su pareja:** `docs/33-decisiones-pendientes.md` — lo que falta por decidir.

---

## 1. Resumen en una frase

Una plataforma donde cualquiera envía el enlace de un vídeo, la IA lo transcribe, separa
quién habla, extrae las afirmaciones verificables, busca fuentes y emite un veredicto; y
donde la comunidad vota, discute en un foro, corrige los nombres de los hablantes y
construye una wiki de afirmaciones — todo con un presupuesto de gasto vigilado al céntimo.

---

## 2. El recorrido de un vídeo, de principio a fin

1. **Envío** (`/submit/`, alias `/analizar/`) — requiere sesión, email verificado y cuota.
   El servidor valida que la plataforma del vídeo esté soportada.
2. **Ficha inmediata** — el título y los datos llegan por oEmbed sin esperar al análisis, así
   que la página existe desde el primer segundo.
3. **Fase barata** (`run_cheap_phase`) — transcripción, diarización y **barrido** de la
   transcripción en lotes de 40 frases (techo de 8.000 tokens por lote) buscando
   afirmaciones verificables. Límite de vídeo: 90 minutos.
4. **Fase completa** (`run_full_analysis`) — búsqueda de fuentes en SearXNG, archivado en
   Wayback y **veredicto** por afirmación.
5. **Publicación** — el análisis aparece en portada, o en la sala +18 si está marcado como
   contenido adulto, o en Off-topic si el clasificador lo relega.
6. **Vida comunitaria** — votos de validación, discusión, propuestas de nombre para los
   hablantes, seguimiento de afirmaciones y notificaciones.

---

## 3. Los agentes de IA y qué modelo usa cada uno

| Agente | Fichero | Modelo (valor real hoy) |
|---|---|---|
| Barrido de afirmaciones | `agents/sweep.py` | Haiku — `claude-haiku-4-5-20251001` |
| Clasificador (off-topic, adulto) | `agents/algorithm.py` | Sonnet — `claude-sonnet-4-6` |
| Veredictos | `agents/verdict.py` | Sonnet — `claude-sonnet-4-6` |
| Moderación | vía `MODEL_CHEAP` | **Solo Haiku** (decisión congelada del README §25) |
| Reescaneo por desacuerdo | `opus_rescan` | Opus — `claude-opus-4-8` |
| Búsqueda de fuentes | `agents/search.py` | SearXNG (no es IA) |
| Diarización (quién habla) | `agents/diarization.py` | pyannote 3.1.1 local (no gasta API) |
| Identidad de personas | `agents/wikidata.py` | Wikidata (no es IA) |
| OCR | `agents/ocr.py` | — |

**Reescaneo con Opus**: cuando más del **40 %** de los votantes discrepa de un veredicto
(mínimo 10 votos), Opus revisa ese fragmento **una sola vez**. Es el mecanismo de apelación.

---

## 4. Lo que puede hacer un usuario

**Cuenta y acceso** — registro con verificación por email (Brevo real), medidor de fuerza de
contraseña en vivo, los 4 validadores estándar de Django, recuperación, ajustes, amigos
(`/amigos/`), bloqueos, mensajes privados con consentimiento (`/mensajes/`), notificaciones
en campana con sondeo y resumen diario opcional.

**Sobre un análisis** — votar validación, discutir, votar frases una a una (`/oracion/…`),
suscribirse a un post, proponer y votar **quién es cada hablante** con autocompletado de
Wikidata (identidad unívoca por QID, homónimos separados), pedir reanálisis (solo
moderación) y seguir una afirmación (`/claim/…/seguir/`).

**Contenido** — portada por secciones, Trending, buscador, wiki de afirmaciones con
historial de versiones y cambios recientes, fichas públicas de persona (`/persona/…`), foro
completo (citas, paginación, salto a lo nuevo, edición 15 min, firma), sala +18
(`/mas18/`), RSS de veredictos y de cambios, y **API v1 pública de lectura**
(`/api/v1/claims/`).

**Idiomas** — español e inglés; el idioma sale del navegador o de la elección explícita, y
el logo cambia con él (escierto./isthistrue.).

---

## 5. El dinero

| Concepto | Valor real hoy |
|---|---|
| Presupuesto diario | **3,00 €** |
| Tope mensual | **100,00 €** |
| Techo duro (no superable) | **200 €** |
| Minutos de análisis gratis | **20** |
| Céntimos por minuto de vídeo | **12** |
| Objetivo de donaciones del mes | **100 €** |

Cada gasto pasa por `try_spend`, que descuenta de `DailyBudget` y `MonthlyCap`; si no hay
saldo, la acción se bloquea. El banner de portada muestra el gasto vivo y permite donar por
PayPal (5 €, 10 € o cantidad libre) sin salir de la página. Las donaciones **suben los
cupos**. Coste anunciado y donación sugerida se calculan sobre los minutos reales del vídeo
(60 min ≈ 2,52 € análisis barato, 4,68 € completo, 5,00 € de donación sugerida).

---

## 6. Moderación y protección

Moderación automática con Haiku sobre cada mensaje; casos a revisión humana
(`ModerationCase`); reportes de mensajes, ocultación, marcado de sensible (5 reportes lo
velan); relegación de análisis a Off-topic **solo manual**; sala +18 cerrada por fecha de
nacimiento — **con la excepción de la cuenta superusuario, que no tiene restricciones**;
niveles por karma (NEW → CONTRIB → VERIF → VET → MOD) con voto de moderador que pesa 5;
registro de auditoría de todo lo que toca el panel; y formulario de reclamaciones con
seguimiento (`ContentComplaint`).

**Límites legales que el código respeta**: no se almacena multimedia de terceros ni huellas
de voz — la diarización solo produce etiquetas por vídeo, nunca una biometría reutilizable.

---

## 7. El panel de administración (`/panel/`)

Siete pestañas con la piel de la web. **26 ajustes vivos** editables sin tocar el servidor,
entre ellos: registro abierto/cerrado, umbral de opinión (70 %), votos para validar (5) y
para rescatar (10), ventana de validación (3 días), umbral de reescaneo con Opus (40 %),
Trending (5 votos / 7 días), minutos gratis (20), céntimos por minuto (12) y objetivo de
donaciones. También: registro de auditoría, donaciones, copias de seguridad, lotes de
códigos de invitación y reclamaciones.

---

## 8. Infraestructura

**Producción** en `/opt/isthistrue`, seis contenedores (web, worker, beat, db, redis,
searxng) en el loopback `127.0.0.1:8090`, detrás del Nginx del host con certbot en tres
dominios. **Espejo** en `/opt/isthistrue-staging` (puerto 8081, apagado por defecto, siempre
en modo simulado y con candado de invitados).

**Diarización**: matriz de versiones fijada (`torch==2.2.2+cpu`, `torchaudio==2.2.2+cpu`,
`numpy==1.26.4`, `pyannote==3.1.1`) con un candado en el Dockerfile que hace fallar la
construcción si el import se rompe.

**Copias de seguridad**: restic cifrado a Google Drive cada noche a las 00:00, incluyendo
un volcado completo de la base de datos; retención 7 diarias + 3 semanales; verificación los
lunes; restauración probada dos veces.

**Estáticos**: WhiteNoise, con `collectstatic` en el arranque del contenedor y un
smoke-test obligatorio tras cada despliegue (CSS 200 y más de 5 KB en cada dominio).

**Calidad**: 101 tests automáticos que deben pasar en GitHub Actions **antes** de que nada
llegue al espejo, y del espejo a producción.

---

## 9. Tareas automáticas

`run_cheap_phase` · `run_full_analysis` · `opus_rescan` y `opus_rescan_segment` ·
`generate_name_proposals` · `relegate_expired_validations` · `archive_wayback` ·
`send_daily_digests` · `check_avatar` · `generate_code_batch`.

---

## 10. Lo que NO existe (para que nadie lo dé por hecho)

- **Telegram**: descartado para siempre.
- **Huellas de voz / biometría**: prohibido sin visto bueno escrito del abogado.
- **Almacenamiento de vídeo o audio de terceros**: no se guarda.
- **Muros de pago**: no hay ninguno; las donaciones son voluntarias.
- **Cobro por densidad de frases**: pendiente de decisión (ver `docs/33`).
- **Aviso a los votantes por vídeos largos**: decidido, aún **no construido**.
- **Turnstile (anti-bots)**: el código está, faltan las claves.
