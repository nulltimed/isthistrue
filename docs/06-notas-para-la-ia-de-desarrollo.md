# Notas para la IA de desarrollo (Fable 5) — estado real tras el primer despliegue (2026-08-05)

> Escrito por el operador de despliegue (Claude Código) tras montar producción y espejo en el VPS.
> Léelo ENTERO antes de tocar código: hay 5 bugs arreglados en main y 3 decisiones de entorno que afectan a todo lo que entregues.

## 1. Cambios de entorno que DEBES respetar en toda entrega futura

1. **Puerto de producción: `127.0.0.1:8090`** (no 8080 — ese puerto lo ocupa ntfy en el host del VPS y es intocable). Espejo: `127.0.0.1:8081`. Ya actualizado en compose, nginx, README, CLAUDE.md, install.md.
2. **La app propia del foro tiene `label = 'forum_local'`** (`apps/forum/apps.py`). El label `forum` pertenece a `machina.apps.forum`. Consecuencias:
   - `makemigrations`/`migrate` y cualquier referencia por label a la app propia usan `forum_local`.
   - Referencias de modelos por string estilo `'forum.ModerationCase'` serían de machina, NO de apps.forum. Usa `'forum_local.ModerationCase'` o imports directos.
3. **Las migraciones iniciales están COMMITEADAS** (`apps/*/migrations/0001_*.py`, accounts tiene 0002). A partir de ahora genera migraciones nuevas encima (0002, 0003…) y commitéalas; no regeneres las existentes. `wiki/0001` lleva `VectorExtension()` como primera operación — no la quites: es lo que da pgvector a las BDs de test y CI.

## 2. Bugs que rompían el arranque o los tests (ya arreglados en main — no los reintroduzcas)

| Síntoma | Causa | Arreglo (commit) |
|---|---|---|
| Web en crashloop: `Application labels aren't unique: forum` | apps.forum vs machina.apps.forum | `label='forum_local'` (8950236) |
| `ModuleNotFoundError: machina.app` | API retirada en django-machina 1.x (instalada: 1.3.1) | `from machina import urls as machina_urls; include(machina_urls)` (211eefe) |
| checks E304/E305 | `analysis.Post.author related_name='posts'` choca con machina `Post.poster` | `related_name='analysis_posts'` (15d16cb) |
| Tests: `type "vector" does not exist` | BD de test nueva sin extensión | `VectorExtension()` en wiki/0001 (a5e7656) |
| Tests de votaciones: `kombu ConnectionError` (amqp) | `config/__init__.py` vacío → los `@shared_task` se registraban en la app Celery POR DEFECTO, no en la de config/celery.py | import canónico en `config/__init__.py` (f4bc829) |

Lección general de los 5: el código se escribió sin ejecutarse de punta a punta. Antes de entregar, arranca el stack y corre los tests (el checklist existe para eso, pero estos 5 no eran "roces": eran errores).

## 3. Estado del CI

`.github/workflows/ci.yml` NO está en GitHub: el token de David solo tiene scope `repo` y GitHub rechaza pushes que crean workflows sin scope `workflow`. El archivo vive en el árbol local (untracked, `.git/info/exclude`) y en `/tmp/ci.yml.pendiente` del VPS. Cuando David dé un token con `workflow`: `git add -f .github/workflows/ci.yml && git commit && git push`, y quita la línea de `.git/info/exclude`. El ci.yml ya usa `forum_local` en makemigrations. Nota: el paso manual `CREATE EXTENSION` del ci.yml es ahora redundante (lo hace la migración) pero inofensivo.

## 4. Entorno de ejecución real (verificado)

- Django 5.0.14, django-machina 1.3.1, celery 5.4, python 3.12-slim, pgvector/pg16.
- Producción: `/opt/isthistrue` (usuario `i`), `.env` con `DEBUG=False`, `MOCK_AGENTS=true` **hasta que David ponga `ANTHROPIC_API_KEY`** (entonces `false`). Turnstile/Brevo/HF sin clave todavía: registro sin captcha real y emails por consola.
- Espejo: `/opt/isthistrue-staging`, `-p staging`, APAGADO por defecto, MOCK forzado por compose. Los dos comparten imagen pero no BD ni volúmenes.
- DNS: isthistrue/escierto/wikitrue → VPS OK. El espejo: el registro real es `staging.xyztserver.com` (añadido como alias en nginx/compose); `stagings` (lo congelado en README §21) NO existe aún — pendiente de David.
- HTTPS activo (certbot) en los 3 dominios de producción; el conf del host es `/etc/nginx/sites-enabled/isthistrue.conf` y ahora lo gestiona certbot (no lo pises con el del repo sin re-ejecutar certbot).

## 5. Verificado funcionando (espejo, modo mock)

Circuito completo: submit YouTube → transcripción [SIMULADO] con SPEAKER_1/2 → PENDING_VALIDATION → voto único de mod (modo arranque) → DONE → claims verdes en wiki con slug → tarjeta PNG → voto de nombre confirmado en solitario (peso 5). Búsqueda, RSS, /metrics, legales, panel (codes/staging/reclamaciones), candado de invitados del espejo: todo 200/OK. Tests: 10/10.

## 6. Deuda técnica / sugerencias detectadas (NO aplicadas — decide tú o David)

- `/panel/` y `/wiki/` sin ruta raíz devuelven 404 (las subrutas funcionan). Un index o redirect mejoraría UX.
- El worker celery corre como root dentro del contenedor (SecurityWarning); un `USER` no-root en el Dockerfile lo callaría.
- `CPendingDeprecationWarning: broker_connection_retry` — añadir `CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True` a settings cuando toque.
- Los tests dejan BD `test_isthistrue` huérfana si se interrumpen: usa siempre `--noinput` (docs aún dicen sin flag).
- `createsuperuser --noinput` no acepta `--birth_date` (User lo tiene null=True: funcionó sin él). Si algún día birth_date se hace obligatorio, añade `REQUIRED_FIELDS`.
- fail2ban estaba desinstalado en el host y se reinstaló según install.md; confirmar con David.

## 7. Ritual de despliegue vigente (recordatorio operativo)

Commit → push a main → (cuando exista) CI verde → encender espejo → `git pull` + migrar + checklist → apagar espejo → producción: `down` → `.bak` con fecha → `git pull` → `up --build -d` → `migrate` → `collectstatic`. El repo de GitHub y `/opt/isthistrue` deben quedar SIEMPRE en el mismo commit.

---

## 8. Fase 3 aplicada (2026-08-05, tarde) — addendum del operador

- El ZIP de la Fase 3 respetó los 5 fixes y el protocolo de migraciones: BIEN. Se aplicó con un solo arreglo del operador: en `docker-compose.yml` el comentario quedó DENTRO de la cadena del puerto (`"127.0.0.1:8090:8000  # ..."`), lo que invalida el mapeo. En YAML, los comentarios van FUERA de las comillas. Vigila esto en futuros ZIPs.
- Migración nueva generada y commiteada: `analysis/0002_post_tags_post_topic.py`. La numeración sigue desde ahí.
- **Deuda de tests (IMPORTANTE)**: la Fase 3 no trajo ni un test. Sin cubrir: presupuesto vivo (`live_monthly_cap`/`live_daily_budget` con donaciones y techo duro 200), API pública v1 (paginación, 404, solo consolidated), verificación de email (token caducado/manipulado), login email-o-nick, anti-spam de alertas (cache 6 h), redirect de `/panel/`. El robot sigue en 10 tests del Hito 2A. Próxima entrega: añade tests de estos circuitos al MISMO archivo/carpeta `tests/`.
- Particularidad observada en el espejo: el pipeline mock registra gasto simulado en `DailyBudget` (banner "0,08 €"). Decide si es intencional (útil para probar el banner) o si el mock debería costar 0,0000; en producción con mock también contaría. No lo toqué.
- `ensure_superuser` funciona y ya se usa en ambos entornos (ADMIN_EMAIL/ADMIN_PASSWORD presentes en los `.env`). El checklist/install.md aún menciona `createsuperuser` en algunos pasos: en el próximo pase de docs, unifica hacia `ensure_superuser`.
- `stagings.xyztserver.com` ya existe en DNS y tiene certificado; `staging` queda como alias tolerado en nginx/compose.
- CI: sigue bloqueado por el scope del token (reintentado hoy, mismo rechazo). `ci.yml` continúa untracked en el workspace y en `/tmp/ci.yml.pendiente`.

---

## 9. Fase 3.2 aplicada (2026-08-05, noche) — addendum del operador

- **Patrón de bug a erradicar: la fusión de rondas.** El ZIP incluía las DOS iteraciones del reparto de modelos (v2 y DEFINITIVO) a la vez: `opus_rescan` definida dos veces en tasks.py (la 2ª pisaba a la 1ª y llamaba `run(post, model_override=…)` — la firma es `run(post, model=None)`: TypeError), `Post.opus_rescanned` duplicado, y `MODERATION_TRIAGE_MODEL`/`MODEL_RESCAN` en settings/.env sin que nadie los lea. Antes de empaquetar un ZIP, busca definiciones duplicadas (`grep -n "def nombre"` por cada símbolo tocado) y config huérfana.
- Decisiones aplicadas por el operador siguiendo el README §25 DEFINITIVO: pivote EN devuelto a Haiku; moderación se queda con MODEL_CHEAP; MODEL_PREMIUM es el único nombre del modelo de reescaneo. **Flecos para ti**: avatares en Sonnet (confirmar con David) y unificar `should_opus_rescan` (suelo 10, lo usa la vista) con `maybe_trigger_opus_rescan` (candado 50 usuarios, huérfana — nadie la llama).
- **El README no debe tener dos §25**: consolida las dos secciones en una sola en la próxima edición.
- Tests: bien traídos (21 total). Dos fallos de AISLAMIENTO arreglados: `AlertasAntiSpam` necesita `cache.clear()` en setUp (la LocMem comparte estado entre tests) y `settings_test` debe forzar `STAGING_MODE = False` (en el espejo el middleware de invitados rompía el test de la API). Regla: un test no puede depender ni del orden ni del entorno.
- `media_serve`: endurecido el anti-traversal (`startswith(root + os.sep)`; sin separador, `../media-staging` pasaba por el prefijo común "media").
- **Ritual actualizado**: tras `collectstatic` SIEMPRE `restart web` — WhiteNoise indexa STATIC_ROOT al arrancar y los estáticos copiados después dan 404. (Nota: hasta esta fase `/static/` estaba roto en producción con DEBUG=False; nadie lo había probado con curl a un .css.)
- Migración nueva: `analysis/0003_post_opus_rescanned.py` (commiteada). Siguiente: 0004.
- Primer ciclo completo con CI real: rojo → diagnóstico → fix → verde → espejo → producción. Funciona.

---

## 10. Fase 3.3 aplicada (2026-08-05) — addendum del operador

- **REGLA NUEVA, la más importante hasta la fecha: construye cada ZIP SOBRE `main` de GitHub, no sobre tu entrega anterior.** El ZIP 3.3 venía montado sobre la 3.2 *sin* los arreglos del operador y reintrodujo TODOS los bugs ya corregidos (opus_rescan duplicado con model_override=, opus_rescanned ×2, settings muertos, pivote en Sonnet, media_serve sin endurecer, tests sin aislamiento, compose 8080, CLAUDE.md con 'forum'). Se aplicó de forma selectiva y no se perdió nada, pero el margen de error crece con cada pase. `git clone https://github.com/nulltimed/isthistrue` y parte de ahí.
- Presupuesto 100/3 aplicado (defaults, .env.example, seed, .env reales). **Los tests de FrenosPresupuesto ahora derivan los límites de `live_daily_budget()`/`live_monthly_cap()`** — mantenlo así: cifras cableadas en tests = CI roto en cada cambio de presupuesto.
- `seed_settings` es create-if-missing (no pisa ediciones del panel): correcto, PERO los cambios de valores por defecto no llegan a BDs ya sembradas. Este pase requirió un UPDATE manual de `budget_base_eur` en espejo y producción. Si un pase futuro cambia umbrales existentes, decide y documenta el mecanismo (¿comando `--update-keys`?).
- Checklist 46 decía "~22 tests": el ZIP no traía tests nuevos (siguen 21). Si prometes tests en la guía, inclúyelos.
- Moderación en mock siempre devuelve flag:false → el checklist 47 no es reproducible por UI en el espejo; se verificó parcheando la respuesta del cliente. Sugerencia: mock sensible al contenido (p. ej. flag=true si el texto contiene '[insulto') para poder probar moderación de punta a punta en el espejo.
- Login de David: causa raíz = .env editado sin `ensure_superuser` posterior (y sin recrear contenedores). Los comandos están en docs/09 y en la guía de activación. Considera un entrypoint que ejecute ensure_superuser en cada arranque del contenedor web para eliminar esta clase de incidencia.

---

## 11. Fase 3.4 aplicada (2026-08-05) — addendum del operador

- **El formato "paquete mínimo sobre main" (tu §10 adoptado) funcionó de maravilla**: cero reintroducciones de bugs, aplicación en minutos. Mantén este formato para siempre.
- Tres arreglos del operador que debes interiorizar:
  1. **Si un parche borra una función, busca sus usos EN LOS TESTS también** (`grep -rn nombre tests/`). La guía mandaba borrar `should_opus_rescan` pero `tests/test_fase3.py::OpusRescan` la usaba — habría sido CI rojo. El test quedó reescrito contra `maybe_trigger_opus_rescan` con `mock.patch.object(tasks.opus_rescan, 'delay')`.
  2. `_brand()` en verification.py: función muerta con `or True` (siempre misma rama). Los restos de experimentos no viajan en un entregable.
  3. `seed_settings` sembraba `opus_rescan_min_votes`, huérfana tras la limpieza: al borrar lógica, revisa también seeds/config asociados.
- **Lección de verificación (me incluyo)**: los curls sin cabecera `Origin` NO detectan el CSRF 403 de navegador tras un proxy TLS. Todo checklist de formularios debe simular navegador (`-H "Origin: https://…"`). El parche CSRF (CSRF_TRUSTED_ORIGINS derivado de ALLOWED_HOSTS + SECURE_PROXY_SSL_HEADER) ya está en settings; NO lo toques al editar ALLOWED_HOSTS-related.
- Estado del reescaneo Opus tras la limpieza: una sola puerta (`maybe_trigger_opus_rescan`, candado min_users=50 + percent 40 + una vez), llamada desde `upvote`. `opus_rescan_min_votes` ya no existe en seeds; el README §25 quedó consolidado (una sola sección; avatares=Haiku confirmado por David).
- ensure_superuser corre ahora en el arranque del web (command del compose): la incidencia de credenciales .env queda estructuralmente cerrada.
- **DNS**: al cierre del pase, isthistrue.xyztserver.com apuntaba a Brevo (CNAME brand.brevosend.com) en vez de al VPS — no es cosa del código; David debe restaurar el A en IONOS. Si algún checklist tuyo falla solo en un dominio, comprueba `dig` antes de sospechar del código.

---

## 12. Pase 3.6 aplicado (2026-08-05, sesión de cierre) — addendum del operador

- Paquete mínimo sobre main, otra vez limpio: **cero arreglos de código necesarios**. Dos pases seguidos sin reintroducciones — el formato queda consagrado.
- Nota de numeración: el 3.5 nunca se entregó como paquete; el 3.6 lo sustituyó explícitamente. Los informes saltan de docs/10 (3.4) a docs/11 (3.6): no busques un informe del 3.5.
- Aplicado: banner XL con botón PayPal real (client-id de David en base.html — SDK cargado UNA vez para toda la web; /donaciones/ NO lo recarga), logo 96px/56px, cookies.html declara el SDK, donation_goal_eur=100 (seed default + update en BDs existentes — mismo patrón create-if-missing de siempre).
- El DNS de isthistrue quedó restaurado por David y verificado sirviendo la web. El episodio Brevo/CNAME está documentado en guia-cerrar-brevo.md (regla: solo TXT).
- Backups: `backup.sh` definitivo con `REPO="rclone:isthistrue:isthistrue"` (el remoto rclone real se llama `isthistrue`, NO `gdrive` — actualiza cualquier doc futura). Programación: cron de root a las 00:00 con RESTIC_PASSWORD inline (decisión aceptada por diseño), retención 7d+3s, `restic check` los lunes.
- Recordatorio vigente para tu próxima entrega: tests SIEMPRE incluidos si los prometes, paquete mínimo sobre main, y grep de usos (incluidos tests/) antes de borrar cualquier símbolo.

---

## 13. Pase 3.7 aplicado (2026-08-13) — addendum del operador

- Paquete mínimo sobre main: tercera vez consecutiva sin reintroducciones. Formato consagrado.
- **Hallazgo de seguridad que se te escapó dos veces**: `AUTH_PASSWORD_VALIDATORS` no existió NUNCA en settings (desde el Hito 2A). Tu diagnóstico del registro mudo ("los validadores rechazaban y nadie lo mostraba") era falso en su segunda mitad: no había validadores y "1234" creaba usuario. El checklist 64 lo destapó porque pedía verificar el recuadro rojo — y no salió. Lección: cuando descrbas una causa en un README de pase, comprueba que el mecanismo que citas EXISTE en el código. Los 4 validadores estándar están ahora en settings (commit 3e1fae0).
- El parche de Turnstile (§2) confirmado como la causa dura: con DEBUG=False y sin claves, `verify()` devolvía False y el registro de producción llevaba BLOQUEADO EN SILENCIO desde el primer despliegue. Patrón a vigilar: cualquier "fail-closed" silencioso alrededor de servicios externos opcionales debe degradar con warning, no bloquear sin mensaje.
- Checklist 65 ejecutado con Brevo real en producción (SMTP sin errores). El flujo verificación→bienvenida→login queda verificado de punta a punta.
- Logo v4 CONGELADO por David: no tocar los SVG sin su orden expresa.
- Recordatorio operativo vigente: backups aún sin activar por David (docs/11); Turnstile sin claves (warning esperado en logs hasta entonces).

---

## 14. Candado de estáticos (2026-08-13) — addendum del operador

- Incidencia "web fea": CSS 404 por recreación del contenedor web fuera del ritual — `/app/staticfiles` vive en el fs del contenedor y CUALQUIER recreación lo vacía. Ya no puede repetirse: el `command` del web ejecuta `collectstatic --noinput` en cada arranque (ambos composes), verificado con recreación forzada. Si tocas los `command` del compose, CONSERVA la cadena ensure_superuser && collectstatic && gunicorn.
- CLAUDE.md tiene nueva sección "CANDADO DE ESTÁTICOS": smoke-test obligatorio tras cada despliegue. Nota: el umbral es >5 KB (el documento de David decía >10 KB pero main.css comprimido pesa ~8 KB; si el CSS crece, actualizad el umbral con cabeza, no a ojo).
- Alternativa más limpia si algún día quieres: volumen para staticfiles o `WhiteNoise` con `WHITENOISE_USE_FINDERS` en arranque; por ahora el collectstatic-en-command es suficiente y simétrico con ensure_superuser.

---

## 15. Favicon v2 (2026-08-13) — nota breve del operador

- Favicon congelado por David en `static/img/` (svg + png 32/180) con sus 3 links en base.html. Si entregas un base.html nuevo, CONSERVA esos links.
- Detalle recurrente en tus guías: el umbral del CSS sigue apareciendo como ">10000 bytes" — el vigente es >5 KB (main.css comprimido = 8206 B). Actualiza tu plantilla de checklist.

---

## 16. Pase 3.8 aplicado (2026-08-13) — addendum del operador

- BIEN: la guía §73 anticipó su propio riesgo y delegó la decisión con el plan B ya escrito — ese es el patrón ideal de entrega. Confirmado el riesgo real: `disabled` cableado en el HTML = registro imposible sin JS. Aplicado el plan B (botón habilitado por defecto; el JS lo desactiva al cargar) + `check()` inicial que faltaba en el script (sin él, con JS el botón nacía encendido hasta el primer input).
- Regla general derivada: en mejoras progresivas, el estado por defecto del HTML debe ser el FUNCIONAL sin JS; el JS restringe, nunca al revés.
- CSS ahora pesa 9071 B comprimido (medidor incluido); el umbral >5 KB del candado sigue valiendo.

---

## 17. Pase 3.9 aplicado (2026-08-13) — addendum del operador

- Entrega limpia; guía con las notas previas interiorizadas. Dos añadidos del operador: (1) `submit` no comprobaba `email_verified` — añadido (la guía lo exigía pero el parche no lo incluía); (2) alias `/analizar/` → vista submit (tu guía nombraba esa URL pero la ruta era solo /submit/; los templates usan {% url 'submit' %}, así que era cosmético — pero si nombras URLs en una guía, entrégalas en el código).
- `HostLanguageMiddleware` eliminado tras verificar con grep que `request.site_section` no tenía más usuarios. Patrón: antes de borrar un middleware con efectos secundarios, inventaria TODOS sus efectos (idioma + site_section en este caso).
- Idioma: cookie (set_language) → Accept-Language → 'es'. El `<html lang>`, título y logo siguen a request.LANGUAGE_CODE. Si añades páginas nuevas, usa {% trans %} desde el principio.
- CSS: 10.186 B comprimido. Umbral del candado (>5 KB) sigue correcto.

---

## 18. Backups activados (2026-08-14) — addendum del operador

- **Hallazgo crítico en TU diseño de backup.sh**: copiaba /opt/isthistrue pero la BD vive en el volumen Docker `pgdata` — el backup no llevaba NI UN dato de usuarios/posts/claims. Arreglado: pg_dump → ops/backup/db-dump.sql.gz antes de cada snapshot (en .gitignore). Lección de arquitectura: al diseñar backups de un stack Docker, inventaria TODOS los volúmenes nombrados; "copiar la carpeta del proyecto" nunca cubre named volumes.
- Diseño final: /root/.restic-pass (600) + RESTIC_PASSWORD_FILE en el script; cron de root 00:00 sin secretos; retención 7d+3s; check los lunes. La contraseña la tecleó David en su terminal: el operador nunca la vio.
- Si un pase futuro toca backup.sh: CONSERVA el pg_dump y el password-file. Y si añadís volúmenes nuevos al compose (p. ej. otro servicio con estado), añadidlos al backup el MISMO día.

---

## 19. Pase 4.1 ejecutado POR EL OPERADOR (2026-08-15) — addendum

- Primer pase entregado como ORDEN DE TRABAJO (sin ZIP): funcionó. El formato "criterios de aceptación + reglas vigentes citadas" es aún mejor que el paquete mínimo — el operador desarrolla y tú revisas main. Repite el formato cuando la tarea sea de infraestructura/integración.
- **Matriz de versiones ML FIJADA en requirements (no tocar sueltas)**: torch==2.2.2+cpu · torchaudio==2.2.2+cpu · numpy==1.26.4 · pyannote.audio==3.1.1, con --extra-index-url de wheels CPU. El candado `RUN python -c "import pyannote.audio"` del Dockerfile convierte cualquier regresión en fallo de BUILD. Si necesitas subir torch: cambia las 4 a la vez, valida el import y actualiza esta nota.
- La causa raíz de B1 era DOBLE (AudioMetaData + numpy 2.x): la segunda solo apareció al arreglar la primera. Patrón: tras fijar versiones, SIEMPRE validar el import real en la imagen, no asumir.
- deno 2.1.4 por ARG en el Dockerfile (sube la versión cambiando el ARG y validando `deno --version` en build).
- base.html: el banner ahora lleva el selector de donación (radios accesibles + input). INVARIANTES nuevas además de las 5.12: el bloque `donate-amounts` + noscript-fallback viajan JUNTOS con el script del SDK capture.
- Admin: override en templates/admin/base_site.html + static/css/admin-skin.css. Si tocas plantillas del admin, solo piel — P6 depende de su estructura.
- Tests: 25 (nuevos: 3 del gate de diarización con sys.modules mockeado + 2 de cantidad de donación). El de fallo de pyannote reproduce el AttributeError histórico como regresión.

---

## 20. Pase 4.2 aplicado (2026-08-15) — addendum del operador

- **El formato parche-sobre-main-real es EL BUENO**: aplicó limpio a la primera. Mantenlo. Pero el CI cazó 6 fallos: dos bugs reales (slug de machina pisado por Topic.save() — TODO C4 dependía de él; autor sin aviso de Trending) y tres de tests (hosts, MOCK a nivel de clase que llamaba a la API real, test antiguo sin actualizar a la semántica A2 que TÚ cambiaste). Regla nueva: **si cambias un comportamiento, actualiza los tests antiguos que lo cubrían en el MISMO parche**; y ejecuta la suite ENTERA, no solo tus tests nuevos.
- **machina Topic.save() regenera el slug desde el subject**: cualquier save de Topic pisa 'post-<pk>'. El glue lo re-fuerza con update() tras crear y tras move_topic. Si añades flujos que guarden Topics, re-fuerza el slug o C4 se rompe en silencio.
- **Ritual nuevo para migraciones que tocan User**: ensure_superuser corre en el arranque del web y consulta el modelo → con campos nuevos sin migrar, el web no arranca. Orden: `compose run --rm web migrate` ANTES de levantar el web. Alternativa estructural a valorar: migrate en la cadena del command del web (decisión para David).
- El espejo NO tiene searxng (diseño): las instrucciones de force-recreate con searxng son solo-producción; escribidlo así en futuras guías.
- reverdict_missing_sources --dry-run → 0 en ambos entornos (los claims existentes tienen sources_ok=True por default de migración, como preveía tu guía). El update manual de los del 15-08 espera la confirmación de David.

---

## 21. Pase 4.3-A aplicado (2026-08-16) — addendum del operador

- Parche limpio a la primera, migración de DATOS incluida y verificada (0 dobles prefijos en ambos entornos). El nivel de entrega sigue subiendo: solo 1 fallo de CI en 47, y era MÍO (el mock del gate de diarización imitaba el prefijo antiguo — me aplico mi propia regla de actualizar tests al cambiar comportamientos; queda actualizado a labels reales de pyannote 'SPEAKER_XX').
- Nota para tus futuros parches de datos: la pareja "fix de código + migración reparadora de lo ya guardado" (I7) es EXACTAMENTE el patrón correcto. Repítelo siempre que un bug haya dejado datos sucios.
- El z-index del sticky (.media-grid vs masthead) queda como aviso conocido para 4.3-B, como anunciaste.
- Recordatorio vigente: espejo sin searxng; migrate efímero cuando toques User (usado en este pase, sin incidencias).

---

## 22. Pases 4.3-A.1 y A.2 aplicados (2026-08-16) — addendum del operador

- **Hito del circuito: CERO arreglos del operador en dos parches consecutivos.** CI verde a la primera en ambos (51/51 y 53/53), checklists K y L completos en espejo, producción sin incidencias. El formato guía-con-checklist-verificable + tests incluidos + migraciones de datos con criterio (purga selectiva verificable antes/después) es exactamente lo que necesita este proyecto. Mantenlo.
- Detalle de calidad de la purga (K3): conservar lo confirmado y lo humano, borrar solo lo automático — y que el operador pueda verificarlo con dos queries. Toda migración destructiva futura: mismo patrón (criterio selectivo + verificable).
- El test de guardia de K5 (escaneo de plantillas contra {# #} multilínea) es el tercer "lección→candado" del proyecto (tras el import de pyannote en build y el smoke de estáticos). Sigue convirtiendo cada lección en un candado ejecutable.
- L6: el atributo data-toast-sound solo se emite con la pref ON — correcto, pero documentadlo en la guía la próxima vez (el operador tuvo que leer el código para distinguir diseño de fallo en el checklist).
- Recordatorio: pendiente de David cancelar la suscripción antigua en el panel de PayPal.

---

## 23. Pase 4.3-A.3 aplicado (2026-08-16) — addendum del operador

- Funcionalidad impecable (M1/M2/M3 tal cual la guía). Los dos fallos estuvieron en el ANDAMIAJE de verificación, y ambos son patrones a evitar:
  1. **Un test que prohíbe una cadena en TODO un archivo** (`assertNotIn('100vw', css)`) choca con los COMENTARIOS que documentan su eliminación. Si escribes un guardián de ausencia, revisa que ni la documentación interna del archivo contenga la cadena — o afina el test para que ignore comentarios. Interceptado antes del push.
  2. **Un test de atributos sobre un escenario vacío**: el post de prueba de M1/M2 no tenía transcripción, así que los data-start/data-end (que emite CADA frase) no existían. Al escribir un test que verifica marcado dependiente de datos, crea esos datos.
- Nada que reprochar al código: `main.wide` + el bloque en base.html es la solución limpia que pedía David, y el resto de páginas conservan su columna (verificado por separado en el espejo).

---

## 24. Pase 4.3-A.4 aplicado (2026-08-16) — addendum del operador

- Entrega impecable: parche limpio, CI verde A LA PRIMERA (58/58), checklist N1-N3 completo, **cero arreglos del operador**.
- **El bonus merece quedar como regla del proyecto**: los `data-*` numéricos renderizados por Django salen con el separador decimal del LOCALE (en español, coma), y `parseFloat` los trunca en silencio. Siempre que un dato numérico viaje de plantilla a JavaScript: normalizar (`stringformat:'s'|cut:','`, o `unlocalize`, o serializar en JSON). Este bug hizo que el seguimiento en vivo del A.3 pareciera "casi funcionar" — el peor tipo de fallo.
- Lección de diagnóstico: N1/N2 se descubrieron con F12 sobre el DOM real, no con tests. Cuando un pase toca maquetación, el checklist debe incluir una inspección del DOM (el operador ahora verifica "X dentro de Y" con un regex sobre el HTML servido, no solo la presencia de clases).

---

## 25. Pase 4.3-A.5 aplicado (2026-08-16) — addendum del operador

- Segundo pase seguido con CI verde a la primera y cero arreglos del operador. Checklist O1-O4 completo; verificado en producción que el post 4 sale ordenado SIN reanálisis, como predecía tu nota.
- **O1 merece entrar en el catálogo de trampas del proyecto**: `.annotate(Count(...))` introduce un GROUP BY que ANULA el `ordering` del Meta en PostgreSQL — el queryset sale en orden de inserción. Cada vez que anotes agregados sobre un modelo con orden natural, añade `.order_by()` explícito. Es el segundo bug "el código parecía bien pero la presentación mentía" tras el de los decimales del A.4.
- O3 (reanalizar) pasa por `try_spend`: bien. Si en el futuro añades acciones de moderador que gasten presupuesto, mantén ese patrón — el candado económico no se salta ni por un mod.
- O4: la funcionalidad ya existía desde el A.3 y solo faltaba visibilidad. Buen recordatorio de que "no lo encuentro" es un bug de diseño, no una petición menor.
