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

---

## 26. Pase 4.3-A.6 aplicado (2026-08-16) — addendum del operador

- Tercer pase seguido con CI verde a la primera y cero arreglos del operador. El README de este pase es el mejor recibido hasta ahora: verificaciones previas reales (parseo de las 9 plantillas con el motor de Django), greps de coherencia que el operador pudo repetir tal cual, smoke con CIFRAS EXACTAS (CSS 25.971 B, panel-tabs≥4, píldora=1) que cuadraron al byte en producción, y una sección "si algo falla" con el diagnóstico de cada test. Mantén ese formato: reduce el trabajo del operador a confirmar, no a investigar.
- **P1 es la lección de diseño del pase**: una funcionalidad sin camino en la interfaz NO existe para el usuario. El interruptor del registro llevaba tres pases "hecho" (A.3 lo creó, A.5 lo destacó) y David seguía sin poder usarlo porque nadie enlazaba /panel/settings/. Cuando entregues una vista nueva, entrega también CÓMO se llega a ella.
- P2: el patrón "texto blanco sobre fondo heredado" muerde cada vez que se invierte un tema. Al añadir un estado oscuro (.live, .speaking), revisa TODOS los hijos con fondo propio (píldoras, botones, velos), no solo el color del texto.

---

## 27. Identidad de hablantes con Wikidata (2026-08-17) — AVISO DE ALCANCE para Fable

- **Lo que tenías anunciado para el 4.3-B (autocompletado Wikidata para nombrar hablantes) YA ESTÁ EN PRODUCCIÓN**: lo pidió David directamente y lo desarrolló el operador. NO lo dupliques; construye encima. Commit `b11c431`, informe en docs/29.
- Lo que hay: `apps/agents/wikidata.py::search_people()` (filtra personas por P31=Q5, devuelve QID+nombre+descripción+foto de Commons, caché 24 h, degradación ruidosa), endpoint `/hablante/buscar/` con login, `static/js/speaker-suggest.js` (progresivo: sin JS el campo es texto libre), y **la identidad anclada al QID** en `apps/wiki/naming.py::_person_for()` — homónimos son fichas distintas, el mismo QID es idempotente. Migración `wiki/0003` (wikidata_id/photo_url/description).
- **Lo que sigue libre en ese frente** (tuyo si David lo pide): normalización Haiku de nombres escritos a mano (para fusionar "pedro sanchez" con la ficha correcta), página pública de persona mostrando sus claims atribuidos (`claims_for_person` ya agrupa por identidad real), y el umbral 5-usuarios/1-mod que ya funciona tal cual.
- Invariantes que NO debes romper si tocas esto: el QID manda sobre el nombre; reescribir a mano borra el QID en el cliente Y el servidor valida el formato `Q\d+`; y la línea roja §4.7 sigue intacta (cero voz, la identidad la ponen los votos).

## 28. Pase 4.3-A.8 aplicado (2026-08-17) — addendum del operador

Aplicado y en producción (commit `69da66e`, CI 100/100). Informe completo en `docs/30`.

**Seis tests del propio pase fallaban por desactualizados** (no por bugs del código): 4 de
CSS —el A.7 fusionó `.segment.live` y `:hover` en reglas agrupadas de dos líneas y los tests
buscaban los selectores sueltos—, 1 de donación —el README fija 5,00 € para 60 min pero el
test exigía `< 5`— y 1 de reescaneo de Opus —el umbral del 40 % es inclusivo (`>=`), así que
el 5.º voto ya dispara, y el test usaba 6 votantes esperando 2 llamadas—. Los alineé con el
comportamiento que el propio pase decidió. **Petición: cuando un pase cambie un umbral o
agrupe reglas CSS, actualiza sus tests en el mismo ZIP.**

### Las tres mediciones que pediste en tu §5

1. **Frases y lotes (✅ medido)**: sobre 4 vídeos reales, la densidad va de **16,1 a 44,1
   frases/minuto** según lo picado del montaje. Extrapolado a 1 hora: **entre ~970 frases
   (25 lotes) y ~2.650 frases (67 lotes)** con `SWEEP_BATCH_SIZE=40`. Dimensiona para el
   rango, no para una media. Caso real medido: 12,6 min → 553 frases → 14 lotes.
2. **Tiempos de whisper+pyannote en 1 h (❌ no disponible)**: ningún vídeo de esa duración se
   ha procesado (el mayor es de 12,6 min) y, sobre todo, **`AnalysisRequest` no guarda
   tiempos**: sus campos son `id, post, user, served_from_cache, created_at`. Si quieres esta
   métrica de forma repetible, **añade `started_at`/`finished_at`** (o registra la duración de
   la tarea Celery); hoy solo vive en los logs efímeros del worker, que se pierden al recrearlo.
3. **Gasto real vs reservado (🟡 parcial)**: `DailyBudget` reservó 0,05 + 0,17 + 0,12 =
   **0,34 €** (14-16 de agosto). El contraste con la consola de Anthropic solo puede hacerlo
   David. Con ese volumen la calibración de `cents_per_video_minute` no será significativa:
   hace falta más tráfico.

### Trampa nueva documentada: la sala +18 y el superusuario

`/mas18/` devuelve **403 a la cuenta de administrador `d`** porque `ensure_superuser` **no
establece `birth_date`** y `is_adult` es False. Es el candado funcionando, no un bug — pero
provoca un falso negativo al verificar: parece que la sala está rota cuando lo que falta es
la edad del verificador. Comprobado con una cuenta mayor de edad real: **200 y menú +18
visible**. Considera si `ensure_superuser` debería aceptar una fecha opcional del `.env`.

### Pendiente de David

La decisión **B4** (donación sugerida para vídeos >20 min = **aviso, no muro**) queda tal
cual está desplegada —aviso— a la espera de su confirmación explícita.

## 29. Decisiones de producto de David (2026-08-17) sobre vídeos largos y densos

Tras leer las mediciones del §28, David ha decidido tres cosas. Las dos primeras son
órdenes cerradas; la tercera te la traslado con un escollo técnico que debes resolver TÚ
en el diseño, porque tal como está enunciada no es implementable.

### 29.1 La cuenta superusuario NO tiene restricciones (YA APLICADO por el operador)

Commit `c765516`. `User.is_adult` devuelve `True` si `is_superuser`, sin exigir
`birth_date`. Motivo: `ensure_superuser` no establece fecha de nacimiento, así que el dueño
de la plataforma se quedaba fuera de su propia sala +18. Como el menú, la vista `/mas18/`,
los filtros de portada y los ajustes cuelgan todos de esa propiedad, el privilegio queda
coherente en toda la web con un solo cambio. **El privilegio es SOLO del superusuario**:
staff y moderadores siguen sujetos a la fecha (fijado con test). No lo revoques en futuros pases.

### 29.2 Vídeos largos: aviso + notificación + email, nunca muro (decisión B4 CONFIRMADA)

> David, literal: «a las personas que hayan votado por analizar un vídeo tan largo, se les
> emitirá una notificación e email de las consecuencias económicas, sin más. El gasto
> entrará en el gasto diario/mensual».

Queda confirmado que la donación sugerida es **aviso, no muro**. Lo que falta por construir
—y es tuyo—:

- Al lanzarse el análisis de un vídeo largo, **notificación en la campana + email** a
  **quienes votaron por analizarlo** (no solo a quien lo envió), explicando el coste que
  supone. Respeta el circuito de preferencias que ya existe: `wants(key)`, silencio
  nocturno (`quiet_night`), digest. Hará falta una clave de preferencia nueva.
- El gasto **entra en `DailyBudget`/`MonthlyCap` como cualquier otro**: no se crea ninguna
  vía de gasto paralela ni se salta `try_spend`.
- El aviso es informativo: **el usuario puede continuar sin pagar**. No añadas muros.

### 29.3 Cobrar por densidad (>40 frases/min) — ESCOLLO: el dato no existe a tiempo

> David, literal: «por eso el exigir al usuario dinero que quiera analizar un vídeo de más
> de 40 frases por minuto».

La intención es clara y está bien fundada: en las mediciones del §28, un vídeo denso (44,1
frases/min) genera **casi 3 veces más lotes** que uno tranquilo (16,1 frases/min) a igual
duración, y hoy los dos pagan lo mismo porque el precio solo mira los minutos. **Pero el
número de frases por minuto NO se conoce antes de transcribir**, y la transcripción es
justamente una de las partes caras. Pedir dinero por adelantado en función de un dato que
solo existe después de gastarlo es imposible tal cual.

Tres salidas posibles (elige tú, o propón otra, y que David confirme):

1. **Precio en dos tramos**: se cobra/sugiere por minutos al empezar y, si al terminar la
   transcripción la densidad supera el umbral, se avisa del sobrecoste y se pide un
   complemento voluntario. Coherente con «aviso, no muro» del 29.2.
2. **Estimación previa por señales baratas**: plataforma, categoría, si es un debate o
   tertulia, duración e histórico del canal (el modelo `Channel` existe y está vacío). Es
   una heurística: acertará a veces.
3. **Reserva por el peor caso**: cobrar/sugerir suponiendo la densidad alta y devolver o
   acreditar la diferencia. Es lo más justo económicamente y lo más incómodo de explicar.

**Dato duro para dimensionar (§28)**: con `SWEEP_BATCH_SIZE=40`, una hora de vídeo son
entre **25 lotes** (16 frases/min) y **67 lotes** (44 frases/min). El umbral de 40
frases/min que menciona David cae justo en la zona alta de lo medido: hoy solo 1 de los 4
vídeos reales lo superaría.

## 30. Registro técnico de las intervenciones del operador (2026-08-17)

Nuevo documento `docs/34-registro-tecnico-intervenciones-operador.md`: los 77 commits del
operador explicados con **causa raíz, mecanismo, corrección y regla derivada**. Es el
complemento técnico de este canal — aquí van los avisos por pase; allí, el porqué de cada
arreglo, con el código.

Lectura recomendada antes de tu próximo pase: **§6, la tabla de 12 reglas permanentes**
(degradación ruidosa, `order_by` explícito con `annotate`, `queryset.update()` para campos
derivados en `save()` ajenos, normalización de decimales plantilla→JS, claves de caché
hasheadas, candado de build para matrices frágiles…).

**Petición formal, repetida aquí porque es la que más trabajo genera**: 8 de las 12
correcciones del banco de pruebas (§5 de ese documento) fueron **tests que el propio pase
dejó desactualizados** al cambiar un umbral, agrupar reglas CSS o alterar un comportamiento
fijado en el README. Cuando un pase cambie cualquiera de esas tres cosas, sus tests deben
viajar actualizados en el mismo entregable.

## 31. Pase 4.3-C aplicado (2026-08-17) — addendum del operador

En producción (commit `e628a99`, CI 116/116 **a la primera, cero arreglos del operador**,
migración de datos incluida). Informe completo en `docs/35`. Checklist de 11 puntos: todo
verde, incluido el detalle fino del `{% block og %}` (encender `wiki_index_people` quita el
`noindex` y **conserva** las etiquetas Open Graph).

### Tus tres preguntas

1. **Tamaño de la wiki el día uno**: producción tiene **1 ficha de `Interlocutor` y 0 con
   QID** → **cero páginas públicas hoy**. La wiki nace vacía y se poblará según se identifiquen
   hablantes.
2. **`0004` sobre datos reales**: `OK` en **1,857 s**, sin traza. **No es prueba de carga**: 1
   fila en producción, 5 en el espejo. El `iterator()` sigue sin ejercitarse sobre volumen.
3. **Tests**: ninguno cayó. Pero son **15, no 17**: la suite quedó en **116**, no en los 118
   que anuncia tu README. Verifiqué los `def test_` del diff para descartar un fallo de
   recolección; es un error de conteo. Lo aviso porque «118 esperados» sería una falsa alarma
   para el siguiente operador.

### Un fleco de diseño que conviene cerrar

Tu checklist 4 justifica dejar cerradas las fichas antiguas diciendo que «nunca se confirmaron
con QID». En producción es cierto (0 con QID), pero **el espejo tenía `Ana Botella` con
`Q41266` y también quedó cerrada**, porque `0004` no reabre retroactivamente. La decisión es
defendible; la justificación no. Decide explícitamente: ¿una ficha antigua **con** QID debe
abrirse al migrar, o esperar revisión manual?

### El método nuevo funcionó

Los seis tests desactualizados del A.7/A.8 no se repitieron, y este era el pase con más
riesgo (migración de datos + rutas movidas + plantillas nuevas). Tus tres cambios —no comparar
cadenas exactas de CSS, contrastar cada número del README contra la aserción, y `grep` del
umbral en `tests/` antes de empaquetar— se notan en el resultado. Mantenlos.

## 32. Pase 4.3-D aplicado (2026-08-17) — addendum del operador

En producción (commit `ace6016`, CI 128/128). Informe completo en `docs/36`. Las dos
migraciones aplicadas en ambos entornos sin incidencias.

### Tus tres preguntas

1. **La búsqueda real de «abascal» FUNCIONA.** Contra la API real, espejo y producción:
   6 personas, **`Q11703587` Santiago Abascal presente**, ninguna película ni empresa.
   Sale en **4.ª posición** (Wikidata ordena por su relevancia, no por fama en España):
   con el apellido solo hay que mirar la lista; «santiago abascal» lo pone primero.
   `sanchez` → 6 personas, todas humanas. El filtro `haswbstatement:P31=Q5` cumple.
2. **`wiki/0005` no abrió ninguna ficha en producción**, y es lo correcto: la única ficha
   (`abascal`) **no tiene QID**, así que sigue en `None` y `/persona/abascal/` en 404. Donde
   sí actuó fue en el espejo: **`Ana Botella` (`Q41266`) pasó de `None` a `True`** — la
   objeción de `docs/35 §3.1` queda resuelta y la regla ya se aplica hacia atrás.
3. **Cayó un test, y era MÍO** — `test_busqueda_filtra_personas_y_degrada_con_aviso`, del pase
   de Wikidata. No es fallo del 4.3-D: mi doble usaba `side_effect` con una **lista de dos
   respuestas**, y `_cirrus_ids` mete una tercera petición en medio; la lista se agotaba, el
   `except` lo degradaba a `[]` y la aserción veía `0 != 1`. **Mismo pecado que te señalé en
   `docs/34 §5`: acoplado a la implementación, no al comportamiento.** Reescrito para
   despachar por el `action` de cada petición; ahora `search_people` puede ganar o perder
   consultas sin romperlo. Ningún test tuyo falló, y los 12 que anunciaste eran 12 exactos.

### Un fleco: la marcha atrás de `wiki/0005` es demasiado amplia

`atras()` revierte a `None` **todas** las fichas con QID e `is_public_figure=True`, no solo las
que abrió la migración. Si se identifican 100 personas y hubiera que revertir, esas 100 se
cerrarían con ellas. Revertir es raro y el daño reparable, así que no bloqueé el pase. Si
quieres precisión, la forma habitual es marcar en la propia migración qué filas tocó (o
acotar por fecha) y revertir solo esas.

### Lo que sí conviene reconocer

El candado AST del `logger` es la clase de defensa que este proyecto necesita: cierra **toda
una familia** de fallos, no el caso concreto. Y el fallo latente que corriges era real —
comprobado en producción antes y después: **ningún post llegó a atascarse en
`CHEAP_RUNNING`**, el fallo estaba armado pero nunca se disparó.

## 33. Pase 4.3-F aplicado (2026-08-17) — addendum del operador

En producción (commit `abec3d9`, **CI 160/160 verde a la primera, cero arreglos del
operador**, con migración y dos tareas horarias nuevas). Informe completo en `docs/37`.
Los 32 tests que anunciaste eran 32 exactos. `beat` reiniciado en ambos entornos y verificado
por `app.conf.beat_schedule`, no por los logs (a nivel INFO no nombra las tareas al arrancar
— apúntalo para futuros checklists: `logs beat | grep <tarea>` da 0 aunque esté cargada).

### ⚠ El presupuesto NO se ha subido, y no es un olvido

Tu checklist §5.2 me pedía poner 150/300. **No lo he hecho en producción**: el CLAUDE.md
tiene una línea roja —«NUNCA subir los límites de gasto sin orden explícita de David»— y una
orden que llega a través de un README tuyo no es una orden directa suya. **Producción sigue en
100/200.** Lo probé en el espejo (mensual 150, diario 4,84 €, umbral 2,42 €: cuadra con tu
README al céntimo) y se lo he pedido a David explícitamente en `docs/37 §1`.

**Consecuencia que conviene que tengas presente al diseñar**: con los 100 €/mes actuales el
umbral es 1,61 €, así que **la cola arranca a los 13,4 minutos de vídeo**, no a los 20 que
calculas con 150 €. Con el catálogo real de David (vídeos de 3 a 13 min) eso significa que la
cola se verá a diario. Si el coste real resultara ser 3 c/min, con 150 € arrancaría a los 81
minutos y casi no se vería. Los tres escenarios están en el informe.

### Dos apuntes

1. **El dinero se renderiza sin céntimos**: el cartel dice «cuesta unos 7,2 €» y «donación de
   7,5 €». El resto de la web usa dos decimales para importes; en un cartel que pide dinero,
   `floatformat:2` es lo esperable.
2. **`.suggesting` está mejor resuelto de lo que anuncias**: dices «el JS lo quita en los
   cuatro caminos que cierran la lista», pero en realidad usas un único
   `classList.toggle('suggesting', !!abierto)` que los cubre por construcción. Es mejor que lo
   descrito — no hay forma de olvidarse de un camino. Descríbelo así, que suma.

### Lo que hay que reconocer del pase

Cazaste **un segundo origen de la verdad que iba a empezar a mentir** (el aviso de presupuesto
agotado comparaba contra `settings.DAILY_BUDGET_EUR`, cableado en 3,00 €) **antes** de que
mintiera. Es exactamente la clase de fallo que cacé yo en `98d3442` con los límites cableados
en los tests. Y la decisión de que **la cola no adelante a los baratos** es correcta y no
obvia: lo fácil habría sido saltarse al primero cuando no cabe.

## 34. Pase 4.3-G aplicado (2026-08-17) — addendum del operador

En producción (commit `6ae077b`, **CI 174/174 verde a la primera, cero arreglos del
operador**). Informe completo en `docs/38`. Sin migraciones, sin `seed_settings`, sin reinicio
de `beat` — tal como anunciabas. CSS 36.202 bytes exactos y 344/344 llaves: los tres números
del README cuadraron al byte.

**Mérito que hay que reconocer**: entregaste esto **sin poder ejecutar la suite** (no tienes
Postgres con pgvector) y salió verde a la primera con 14 tests nuevos y la plantilla del hilo
reescrita. Compensarlo verificando compilación, las 44 plantillas contra el motor real, las
llaves del CSS y la lógica de tus propios candados fue la decisión correcta.

### Verificación con datos exigentes

Creé **22 mensajes** en el hilo del post 2 del espejo para forzar la paginación: ficha de autor
en los 20 de la página (nivel «Verificador», karma 320, «Mensajes: N»), 20 anclas
`id="msg-<pk>"`, acciones con palabras (Citar 21 · Editar 20 · Reportar 20), y **la numeración
NO reinicia**: página 1 → #1…#20, página 2 → #21 #22. Vista previa: 200, `**hola**` →
`<strong>`, `<script>` escapado, 302 sin sesión.

### Casi te reporto un bug que era un acierto — documéntalo mejor

Al pedir la página sin `?pagina=`, el hilo **no abre siempre en la primera**. Lo vi como
inconsistencia (mi primera petición dio #1…#20 y la segunda #21 #22, sin tocar nada) y estuve
a punto de reportarlo. Es tu lógica de `_thread_page()`: aterriza en la página del primer
mensaje **no leído**, y la propia visita registra el `TopicRead`, así que la segunda petición ya
no tiene nuevos y cae en la última página. **Es correcto y es lo que hace cualquier foro** —
pero tu README no lo menciona, y un operador con prisa lo habría reportado como fallo o, peor,
lo habría «arreglado». Un renglón en el checklist («sin parámetro aterriza en el primer no
leído; la segunda visita irá al final») lo evita.

### Dos apuntes de verificación para el checklist

1. **`?page=2` parece funcionar y no funciona.** El parámetro es `pagina`; `page` se ignora y
   cae en la rama «última página», que con 22 mensajes devuelve #21 #22 — exactamente lo que
   uno esperaría de la página 2. Un checklist que diga «prueba `?page=2`» daría un falso verde.
2. **Los grep de una línea no valen contra este CSS.** Reglas como `.md-toolbar button{…}`
   ocupan tres líneas, así que `grep -o '\.md-toolbar button{[^}]*}'` no encuentra nada y
   parece que el arreglo no está. Es la segunda vez que me pasa (también en el 4.3-F con
   `.suggest-list`). Cuando el checklist pida comprobar una propiedad CSS, indica el número de
   línea o usa `grep -A3`.

## 35. Pase 4.4-A.2 aplicado (2026-08-23) — addendum del operador

En producción (commit `75b1e38`, CI **190/190** al tercer intento). Informe en `docs/40`.
Imagen reconstruida y `accounts/0005` aplicada **con el web parado** en ambos entornos, como
manda el ritual cuando se migra `User`. El catálogo funciona: en producción, sin sesión,
`Accept-Language: en` da `>Home<` y sin cabecera `>Portada<`, en los dos dominios.

### 🔴 Un fallo del parche que había que corregir antes de desplegar

El `command` del web quedaba así:

```sh
ensure_superuser && compilemessages --ignore=venv || true; collectstatic && gunicorn
```

Tu intención (degradar si falla la compilación del catálogo) es correcta, pero **en `sh` el
`|| true` no se aplica solo a `compilemessages`: se aplica a `A && B` entero**. Con eso, un
fallo de `ensure_superuser` —el caso clásico de una migración pendiente, que es justo lo que
la regla del `run --rm web` existe para evitar— **dejaba arrancar el contenedor sin
superusuario y sin traducciones, en silencio**. Es fail-open donde el proyecto lleva un año
siendo fail-closed. Comprobado con `sh` en los tres escenarios:

```
tu cadena, si ensure_superuser falla → collectstatic, gunicorn   ← ARRANCA
agrupada,  si ensure_superuser falla → (nada)                    ← no arranca ✔
agrupada,  si solo falla compilemessages → todo sigue            ✔
```

Corregido con llaves: `ensure_superuser && { compilemessages || true; } && collectstatic && gunicorn`.
**Regla general**: en `sh`, `||` y `&&` asocian por la izquierda sin precedencia entre sí. Si
quieres tolerar SOLO un eslabón de una cadena, agrúpalo con `{ ...; }`.

### Dos arreglos en tus tests

1. **Los 16 fallaron de golpe**: el `setUp` de `Pase44A` usa `cache.clear()` y `cache` no está
   importado a nivel de módulo en `tests/test_pase42.py` (el único import vive dentro de un
   método de otra clase). `NameError` en los 16.
2. **Uno dependía del orden de ejecución**: `test_los_correos_siguen_en_castellano_por_defecto`
   recibía inglés. Tu código es correcto (sin idioma elegido, manda el idioma ACTIVO), pero
   **el idioma activo es estado global del hilo**: las peticiones con `Accept-Language: en` de
   los tests anteriores lo dejan activado y el cliente de pruebas no lo restaura. El `setUp`
   parte ahora de `settings.LANGUAGE_CODE`. **Apúntatelo para cualquier test futuro de i18n**:
   sin reset explícito, el resultado depende del orden alfabético de los nombres de los tests.

### Verificado lo que pedías comprobar

Contenido del usuario intacto con la web en inglés (título del vídeo y mensajes del hilo);
idioma del perfil por encima del navegador y vuelta a «Automático»; selector de cabecera vivo
apuntando a `/accounts/idioma/`; correos en «Verify your account» / «Verifica tu cuenta» según
el perfil; las cinco legales en ambos idiomas con su marca de revisión visible para David.

### Nota de verificación para tus checklists

Tu §4.3 propone `curl http://127.0.0.1:8081/` directo contra el espejo. **Eso siempre da 302**:
el espejo tiene candado de invitados y toda URL no exenta redirige. Los checks del espejo hay
que hacerlos con sesión (credenciales ADMIN de su `.env`) o contra producción.

## 36. Pase 4.4-B aplicado (2026-08-23) — addendum del operador

En producción (commit `f6b2e86`, CI **208/208**). Informe en `docs/41`. Los tres fallos
encadenados quedan corregidos y **los semáforos ya se ven**: 26, 12 y 32 veredictos enlazados
en los posts 2, 3 y 4, con la señal barata desaparecida. Los cinco ajustes sembrados.

### El parche no aplicaba: dos pases en paralelo sobre el mismo fichero

Lo entregaste sobre `b5e8423` diciendo que el 4.4-A.2 y este «no se tocan en ningún archivo».
**Sí se tocan**: ambos añaden una clase al final de `tests/test_pase42.py`. 19 de 20 ficheros
limpios; ese falló. Resuelto con `git apply --3way` (mecánico y verificable) — no a mano, que
la norma lo prohíbe. **Petición**: cuando entregues dos pases en paralelo, asume que el fichero
de tests colisiona siempre y dilo en el README; con eso me ahorro el diagnóstico.

### Tres defectos que hubo que corregir

1. **El aviso del pie no se veía en NINGÚN post normal.** Vivía dentro del bloque
   `{% if post.category == 'OFFTOPIC' %}`, así que solo asomaba en los relegados. **El bug es
   anterior a tu pase** (la frase vieja también estaba dentro): corregiste el texto y heredaste
   la ubicación. Lo cazó tu propio test. Movido fuera.
2. **Seis cadenas nuevas sin traducir + los tres estados del semáforo.** El candado i18n del
   4.4-A.2 hizo su trabajo. Añadidas las nueve al `.po`. **Los `choices` van por variable
   (`{% trans s.claim.get_color_display %}`), así que el candado NO los ve**: cuando añadas
   estados nuevos, añádelos al catálogo a mano o saldrán en castellano dentro de la web inglesa.
3. **La suite pasó de 5 s a 326 s.** `search_with_status` duerme `search_retry_seconds` (20 s)
   de verdad, también en tests. Bajado al mínimo en `settings_test`: 26 s. **Regla: ningún
   camino con `time.sleep` debe ejercitarse a velocidad real en el banco de pruebas.**

### Dos correcciones a tu README de operador

- **«Reconstruir imagen: NO (el Dockerfile no cambia)» es incorrecto.** El `Dockerfile` hace
  `COPY . .` y el único volumen es `media`: **el código vive DENTRO de la imagen**. Sin
  `build`, el contenedor arranca con el código anterior y `migrate` responde «no migrations to
  apply» con las dos migraciones sin aplicar — que es exactamente lo que me pasó. **Todo pase
  necesita `build`, cambie o no el `Dockerfile`.**
- Tu §5.6 propone comprobar la búsqueda con `docker compose exec -T web python -c ...`. En el
  espejo eso devuelve el mock (MOCK_AGENTS=true) y no prueba nada del arreglo real. Para
  ejercitarlo hay que forzar `MOCK_AGENTS=False` con un doble de `httpx`, como hice.

### Un error mío, por si vuelve a pasar

Al mover el aviso escribí la explicación como `{# ... #}` **de cinco líneas**. Django solo
admite ese comentario en una: el resto se interpreta como plantilla y el `{% if %}` que puse de
ejemplo dentro del texto quedó sin cerrar → `TemplateSyntaxError` y 23 tests en rojo. Es la
trampa que este proyecto documenta desde el 4.3-A.1. Reescrito en comentarios de una línea.

### Lo que espera decisión de David

La reverificación (§6 de tu README). Simulada sin gastar: **1,64 € en total** (post 2: 0,94 · post
4: 0,39 · post 3: 0,23 · post 1: 0,08). **No la he lanzado**: gasta dinero real y la orden me
llega por tu README, no por él. Se lo he pedido en `docs/41 §5` con tu consejo de empezar por
el post 4. Mientras tanto, **los 96 claims siguen mostrando el veredicto viejo** —los 32 del
post 4 en ⚪ y los 96 con `sources_ok=True`—, que es el retrato exacto del fallo F2.

## 37. Pase 4.4-C aplicado (2026-08-23) — addendum del operador

En producción (commit `88fdcb9`, CI **221/221**). Informe en `docs/43`. Las dos migraciones,
los 13 ajustes y el reinicio de `beat`, hechos. **Se nota que incorporaste las lecciones del
4.4-B**: tu README ya exige reconstruir imagen «SÍ, SIEMPRE» y reiniciar `beat`. Gracias — eso
ahorra media hora de diagnóstico por pase.

### 🔴 Regresión: reescribiste `apps/panel/tasks.py` desde cero

El fichero pasó a contener **solo** `check_models`. Desaparecieron:

- `generate_code_batch` — la tarea que genera los lotes de códigos canjeables (README v2 §7);
- `BATCH_BG_THRESHOLD = 10000`.

**`apps/panel/views.py:6` importa las dos**: `from .tasks import BATCH_BG_THRESHOLD,
generate_code_batch`. El `ImportError` no rompía «los códigos»: tumbaba el **módulo de vistas
entero**, es decir, TODO el panel. Lo cazó el CI en el paso de `makemigrations`.

Restauradas ambas piezas literalmente, conservando tu vigía. Y pasé un barrido AST comparando
los símbolos de nivel superior antes/después en **los 16 módulos .py del pase**: ningún otro
perdió nada.

**La regla que esto deja** (y que ya estaba en el CLAUDE.md como «fusión de rondas», de la Fase
3.2): cuando un pase escriba un fichero que ya existe, el parche debe **añadir**, no sustituir.
Si de verdad hace falta reescribirlo entero, dilo en el README y lista lo que se conserva —
así lo verifico antes de subirlo en vez de descubrirlo por el CI.

### Verificado de tu checklist

`/panel/modelos/` con las seis tareas y sus dos ruedas; el coste estimado se mueve de verdad
(Sonnet **0,75 €/h** → Opus 4.8 **1,19 €/h**); el aviso de las 24 h sale al poner los veredictos
en lotes; el vigía responde «6 comprobados, 0 caídos»; `comprobar-modelos` cargada en
`beat_schedule`; `transcript_dossier` arma la ficha + la transcripción con `[mm:ss]`; y
`Claim.model_used` existe.

**En producción dejé la configuración intacta** (Sonnet, 0,75 €/h) y **no lancé el vigía a
mano**: haría llamadas reales y, aunque sean céntimos, el dinero lo autoriza David. Correrá
solo esta noche.

### Sobre el `models_catalog.py` que dices haber borrado

No existía en ninguno de los tres árboles ni tiene historia en git, así que no había nada que
limpiar por mi parte. Si lo viste en un contenedor, era de tu entorno, no del despliegue.

## 38. Pase 4.4-D aplicado (2026-08-23) — addendum del operador

En producción (commit `8d00e2c`, **CI 229/229 verde a la primera, cero arreglos del operador**).
Informe en `docs/44`. Sin migraciones. Apliqué de entrada el barrido AST de símbolos que dejó el
4.4-C: `tasks.py` y `views.py` sin pérdidas.

Verificado tu checklist entero: el moderador relanza en solitario y **dos veces seguidas** (el
candado no le aplica), con dos `force_deep_scan` en auditoría; el usuario normal ve «Discuto»,
**no dispara** y **sí se le registra el voto** para sumar hacia los 5. En producción dejé el
botón sin pulsar: gastaría dinero real y eso lo autoriza David.

### 🔴 El hallazgo que importa más que el pase: no hay buscador

Al verificar producción vi que el post 4 pasó de 32 grises a **18 anclajes, 16 de ellos
`UNDECIDED`**. Alguien lanzó la reverificación — y el resultado destapa la causa raíz. Se lo
pregunté a SearXNG:

```
unresponsive_engines: brave      → Suspended: too many requests
                      duckduckgo → CAPTCHA
                      google cse → Suspended: too many requests
                      startpage  → Suspended: CAPTCHA
```

Solo responde Wikipedia, y solo a palabras sueltas. `search_with_status('ocupados agricultura
EPA')` → **0 resultados, ok=False**. 117 avisos de suspensión en 30 minutos.

**Tu arreglo del 4.4-B funciona**: el sistema ya no da la búsqueda vacía por buena y dice 🔍 en
vez de mentir con ⚪. Pero la causa raíz es de infraestructura, no de código: **3-5 búsquedas por
afirmación × 84 frases ≈ 300 consultas en minutos desde una IP** es exactamente el patrón que
cualquier buscador corta con CAPTCHA. Los reintentos con espera no lo arreglan: reintentar
contra un motor que te ha puesto un CAPTCHA no lo levanta, y encima consume tiempo.

**Esto condiciona tu diseño del semáforo**: mientras no haya buscador, TODA reverificación
producirá 🔍 y gastará dinero para nada. Tres caminos, por orden de solidez:

1. **Clave de API de búsqueda** (Brave Search API: 2.000 consultas/mes gratis, sin bloqueos
   porque te identifica). Una variable más en el `.env`, como `ANTHROPIC_API_KEY`. Es la
   solución real.
2. **Ir directo a la fuente**: INE y BOE publican sus propios datos; `official_sources` ya lista
   los dominios. Un adaptador por organismo evita el intermediario que se bloquea.
3. **Bajar el volumen**: una sola consulta por afirmación en vez de 3-5, y espaciarlas. Reduce
   el problema, no lo elimina.

Lo he dejado en manos de David (`docs/44 §2`) por ser decisión de producto y de gasto: yo no
cambio por mi cuenta la configuración de motores, que es el corazón de la verificación.

**Y una advertencia para el próximo pase**: no tiene sentido afinar el semáforo ni añadir
estados nuevos mientras la base documental esté a cero. Primero el buscador.

## 39. Pase 4.4-E aplicado (2026-08-23) — addendum del operador

En producción (commit `a54e670`, CI 236/236 al tercer intento). Informe en `docs/45`. El
circuito nuevo funciona: `verdict.py` ya no menciona SearXNG, el reanálisis tampoco, y
`web_searches_per_claim=3` sembrado en ambos entornos. Ninguno de tus 7 tests falló — los tres
fallos eran de pases anteriores, algo esperable al cambiar el circuito de verificación entero.

### 🔴 Se perdió «sin fuentes no hay color», y la cazó el test del 4.4-B

En el 4.4-B la garantía era **estructural**: búsqueda vacía → no se llamaba al modelo → el claim
quedaba `UNDECIDED`. Al mover la búsqueda dentro del modelo, lo único que quedó fue una frase en
el prompt: *«Si no encuentras nada útil: UNDECIDED»*. **Un ruego no es un candado**: `verdict.run`
guardaba `v['color']` tal cual y `upsert_claim` no lo revisa, así que un `GREEN` con
`sources: []` se publicaba con `sources_ok=False` como única señal — el mismo fallo que
arreglamos hace dos días, entrando por otra puerta.

Restaurado en `verdict.py`: `if not tiene_fuentes: v['color'] = 'UNDECIDED'` antes de
`upsert_claim`. **Regla general para lo que viene**: cuando muevas una garantía del código al
prompt, deja el candado en el código igualmente. El modelo obedece casi siempre; «casi» no vale
en una web de verificación.

### Tu §5 resuelto sin gastar: consulté la referencia de la API

Pedías validar los seis modelos «con una llamada por modelo». No hizo falta:

- **Los seis IDs son válidos** (`claude-haiku-4-5-20251001`, `claude-sonnet-4-6`,
  `claude-opus-4-6/4-7/4-8`, `claude-fable-5`). Yo mismo dudé al ver los `4-x` y lo verifiqué.
- Usas **`web_search_20250305`**, la variante básica: soportada de forma general, Haiku incluida.
  Correcto y conservador.

**Mejora concreta para el próximo pase**: los modelos actuales (Opus 4.6/4.7/4.8, Sonnet 4.6)
soportan **`web_search_20260209`**, que acepta **`allowed_domains`**. Con eso, «primero
organismos oficiales» dejaría de ser una instrucción de texto y pasaría a ser una restricción de
la herramienta — `official_sources` ya tiene la lista. Es exactamente la misma lección del punto
anterior: candado en vez de ruego. Ojo: esa variante requiere modelo compatible, así que hay que
elegirla según la columna `web` del catálogo, no fijarla a ciegas.

### La factura, medida

El panel pasa de **0,75 €/hora** (4.4-C) a **3,83 €/hora**: ×5. Coste real **6,4 c/min** — el
panel sigue asumiendo 12, así que reserva de más, que es el lado seguro; tu sugerencia de bajar
a 8 deja margen razonable. **El dato que conviene que tengas presente al diseñar**: con los 100
€/mes actuales de David, el presupuesto de un día entero (3,23 €) **no cubre un vídeo de una
hora** (3,83 €), y la cola arranca a los 25 minutos. Se lo he puesto en `docs/45 §3` con la
tabla de escenarios; la decisión es suya.

## 40. Pase 4.4-F aplicado (2026-08-23) — addendum del operador

En producción (commit `dc68fa6`, **CI 240/240 verde a la primera, cero arreglos del operador**).
Informe en `docs/46`. El parche entró limpio sobre el 4.4-E: no hizo falta el 3-way que
anticipabas — tus tests van al final pero el hunk de contexto seguía casando.

### Tu arreglo funciona, probado con el caso real sin gastar

Reproduje la situación del post 5 ejecutando `merge_into_sentences` con turnos sintéticos:

```
turno largo SPEAKER_00 (0-30 s) + microturno SPEAKER_01 (10-11 s):
  SPEAKER_00: Frase del dominante.
  SPEAKER_01: Get out.               ← antes se lo quedaba el envolvente ✔
fragmento a caballo de dos turnos → se parte por palabras ✔
sin diarización → no fragmenta ni etiqueta ✔
```

Y el síntoma que describías está confirmado con datos de producción: el post 5 tenía **565 de
597 frases (95%) atribuidas a SPEAKER_00**, 30 al segundo y 2 al tercero.

### 📊 Los tiempos reales de whisper+pyannote, POR FIN

Lo pediste en el 4.3-A.8 y no había forma de medirlo. Tu propio cronómetro del 4.4-C lo ha
capturado en el post 5 (22,8 min de vídeo):

```
transcribir (whisper):     999,3 s  (16,7 min)
diarizar (pyannote):     2.058,8 s  (34,3 min)   ← el doble que transcribir
fase barata completa:    3.102,6 s  (51,7 min)
```

**Analizar cuesta 2,3× la duración del vídeo en tiempo de servidor**, y **dos tercios se los
lleva la separación de voces**. Una hora de vídeo ≈ 2,3 horas de proceso. Dos consecuencias
para tu diseño: (1) el aviso de «esto tardará» debería hablar de horas, no de minutos, en
vídeos largos; (2) si alguna vez hay que recortar, el objetivo es pyannote, no whisper.

### Regla de operación nueva (culpa mía, la asumo)

Recreé los contenedores con el post 5 **en plena fase cara** y la tarea se perdió (Celery
`acks_late=False`). Tu `relaunch_stuck_analyses` existe pero el umbral son **6 horas**, así que
no lo rescata hasta la madrugada. Añadido al ritual del handoff: **comprobar
`CHEAP_RUNNING`/`FULL_RUNNING` antes de tocar producción**.

**Sugerencia para ti**: con la fase barata durando ~52 min en un vídeo de 23 minutos, un umbral
de 6 horas es razonable para vídeos largos pero deja mucho tiempo muerto en los cortos. Un
umbral proporcional a la duración del vídeo (p. ej. 3× el tiempo esperado) rescataría antes sin
arriesgarse a relanzar algo que solo está tardando.

## 41. Diagnóstico de la diarización (2026-08-23) — para el próximo pase

David reanalizó el post 5 con el 4.4-F ya desplegado y los tres síntomas siguen: el interlocutor
se atribuye al dominante, aparece un «hablante 3» inexistente y casi todo cae en el primero.
**Diagnóstico completo con mediciones en `docs/47`.** Resumen para que no repitas mi camino:

### Tu arreglo funcionó, pero el problema de fondo es anterior

Por número de frases el reparto mejoró (95/5 → 73/17). **Por tiempo de voz sigue en 91/8**: al
segundo hablante le llegaron muchos trocitos cortos (0,74 s de media), no sus intervenciones.
Mide siempre en segundos, no en frases — el recuento de frases engaña justo aquí.

### Causa principal, medida: pyannote sin `num_speakers`

`diarization.py` llama a `pipeline(audio)` **sin parámetros**. Experimento sobre el mismo tramo
de 3 min:

```
como hoy (automático):        39 turnos · 94,8 % / 5,2 %
con num_speakers=2:           51 turnos · 84,8 % / 15,2 %   ← +190 % el segundo
con num_speakers=2 + WAV 16k: 52 turnos · 86,3 % / 13,7 %
```

**`min_speakers=2` es una línea y triplica la presencia del interlocutor.** Recomendado como
mínimo seguro (en un vídeo conversado nunca hay una sola voz).

### El formato del audio NO es el problema (mi hipótesis, refutada)

Sospechaba del MP3 con pérdida frente al WAV 16k mono que pyannote espera. **Medido: 13,7 % vs
15,2 %, dentro del ruido e incluso peor.** No pierdas tiempo ahí.

### El «hablante 3» es un cajón de sastre

12 fragmentos, **7,7 s en total**, 0,64 s de media: «Mm», «Nice.», «the way.», «Mm-hmm.». No es
una voz: es lo que el clustering no sabe clasificar. Regla propuesta: un hablante por debajo del
1 % del tiempo (o ~10 s) se absorbe, no se muestra.

### 🔴 Tu corte por palabras necesita un suelo

**212 de 748 frases (28,3 %) son de UNA sola palabra; el 50,7 % duran menos de 0,8 s.** Aparecen
líneas sueltas «And», «century», «It», «-hmm.». Dos daños: la transcripción se lee a trompicones
y —más grave— **la fragmentación alimenta el problema de arriba**, porque cuanto más corto es el
trozo menos fiable es el reconocimiento de voz. Propuesta: no cortar por debajo de ~0,8 s ni
dejar frases de una palabra; pegar el resto a la frase vecina del mismo hablante.

### Dato para afinar backchannels

Hay **81 reacciones breves** («Right», «Whoa», «Nice», «Okay», «I love it») y **62 se le
atribuyen al que monologa**. Heurística barata: una reacción de una palabra rodeada por dos
intervenciones largas del MISMO hablante es casi seguro **del otro** — nadie se contesta a sí
mismo.

## 42. 🔴 La vía de lotes quedó a medias y el panel de modelos no manda (2026-08-24)

**Encargo completo, con los dos bloques (diarización + lotes), en `docs/48`.** Este addendum es
el aviso corto; el material para codificar está allí.

El reanálisis del post 5 estuvo **2,6 h sin producir un solo veredicto** y le quedaban 3,4 más.
Lo detuve. Causa:

1. **`batch.py` no se migró en el 4.4-E.** `verdict.py` ya usa `call_search_json` (el modelo
   busca), pero `apps/agents/batch.py:17` sigue con `search.search_with_status` — SearXNG,
   bloqueado desde el 4.4-D. Con `search_retries=2` y espera de 20 s:
   `90 afirmaciones × 4 consultas × 3 intentos × 20 s = 6 horas` de esperas vacías, y el lote
   se habría enviado **sin fuentes** → 90 claims en 🔍 por el candado del 4.4-E.

2. **🔴 El panel de modelos NO gobierna esa rama.** `/panel/modelos/` muestra
   `delivery_verdict = direct`, pero `apps/analysis/tasks.py:215` decide con
   `settings.USE_BATCH_API`, que está en `true` en el `.env`. **David lleva dos días viendo
   «En el mostrador» mientras el sistema usaba «Por correo».**

   Es el cuarto caso del mismo patrón en este proyecto —andamiaje montado, obra sin conectar:
   `{% trans %}` sin catálogo, `logger` inexistente, página de persona inalcanzable— pero este
   es peor: **el panel no está roto, está mintiendo**. Pido dos cosas: que
   `delivery_for('verdict')` sea la única fuente de verdad (y `USE_BATCH_API` quede como valor
   de siembra), y **un test de coherencia panel↔código** que recorra las tareas y falle si lo
   que decide el código no es lo que muestra el panel. Ese candado cazaría de golpe cualquier
   otra rueda desconectada.

El post 5 queda en `PENDING_VALIDATION` con **transcripción y hablantes intactos** (748 frases):
al retomar los veredictos no hay que repetir los 52 minutos de fase barata.

## 43. Pase 4.4-G aplicado (2026-08-25) — addendum del operador

En producción (commit `518d3c7`, **CI 272/272 verde a la primera, cero arreglos del operador**).
Informe en `docs/50`. **Los seis puntos de mi encargo `docs/48` están hechos**, y dos mejor de lo
que yo había propuesto. Migración `analysis/0011`, sin `beat`, sin ajustes nuevos.

### Lo que resolviste mejor que mi propuesta

Pedí `min_speakers=2` a secas. Tu `diarization_hint` distingue cinco casos y **blinda los
monólogos con `num_speakers=1`** — mi versión habría inventado un segundo hablante en un vídeo
de una sola voz. Comprobados los cinco en el espejo, correctos.

Y `reassign_backchannels` **no reasigna cuando no hay otro hablante conocido**: no inventa. Lo
probé a propósito con un solo hablante en la lista y se quedó quieto. Correcto.

### B.2 cerrado como pedí, con el candado incluido

`tasks.py` decide con `delivery_for('verdict')`, `settings.USE_BATCH_API` ya no aparece en
`apps/`, y el test `test_el_panel_muestra_exactamente_lo_que_el_codigo_decide` pone el CI rojo
si el panel y el código divergen. **Ese candado es lo que pedía**: caza cualquier otra rueda
desconectada, no solo esta. Y el detalle de marcar «solo en el mostrador» las cuatro tareas que
no admiten lotes evita el problema por el otro lado: no ofrecer lo que no existe.

### El ajuste que sí toqué en producción, y el criterio

Puse `min_identified_speakers_percent` a **65** (la fila existente en `50` habría dejado el pase
a medias en silencio). Criterio que aplico y que conviene que conozcas: **los ajustes de dinero
no los toco nunca** (presupuesto, panel de modelos: los pone David); un umbral de calidad que el
propio pase cambia de fábrica sí lo alineo, y se lo digo en el informe con cómo revertirlo.

### Dos cosas para el próximo pase

1. **El supuesto de la búsqueda web dentro de `messages.batches.create` sigue sin validar.** No
   lo he probado: cuesta céntimos y el dinero lo autoriza David. Tu degradación a la vía directa
   con WARNING está bien puesta, así que el riesgo es bajo — pero sigue siendo un supuesto.
2. **La medida del bloque A no está hecha todavía**: hace falta rehacer la fase barata del post
   5 (52 min de CPU) para ver si el 91/8 en **segundos de voz** se corrige. Se lo he recomendado
   a David con la llave inglesa → «Transcripción y voces». Hasta que eso ocurra, los arreglos de
   voces están verificados en laboratorio pero no sobre el caso real.

## 44. Pase 4.4-H aplicado (2026-08-26) — addendum del operador

En producción (commit `0da2006`, **CI 279/279 verde a la primera, cero arreglos del operador**).
Informe en `docs/51`. Sin migraciones; `diarize_second_pass_skew_percent=20` sembrado.

### El dato que cierra el diagnóstico del 4.4-G

El reanálisis de David terminó a las 00:08 y confirma tu lectura: de tus tres arreglos de voces,
**dos funcionaron y el tercero no llegó a actuar**.

```
                  23-ago    25-ago (4.4-G)
frases              748         404      ← suelo mínimo ✔
hablante fantasma    12           0      ← absorbido (12,8 s) ✔
SPEAKER_00        90,7 %      91,9 %     ← sin cambio ✗
```

Registro: `Diarización con pista de voces: ninguna (automático)`. La datación no dio confianza
alta y todo el bloque A.1 quedó sin efecto — exactamente lo que este pase corrige.

### Verificado de este pase

Los seis casos de `diarization_hint` (media abre rango; un «1» dudoso ya no blinda; el monólogo
con confianza alta sigue blindado) y los cinco de `second_pass_speakers`, incluido el caso real
del post 5 con sus números exactos (91,9/8,1 → repite con `num_speakers=2`). **Los dos casos que
protegen** —monólogo de una sola voz y número ya fijado por moderación— devuelven 0 como deben.

### Nota de diseño que conviene conservar

Que la segunda pasada mire **el resultado** en vez de confiar en la pista previa es la decisión
correcta: es la diferencia entre pedirle al modelo que acierte y **comprobar si acertó**. Es la
misma lección del 4.4-E («candado en el código, no ruego en el prompt») aplicada a pyannote.

### Fleco menor detectado (no bloquea)

`analysis_times()` devolvió `fase_barata_s: -179490.7` durante el relanzado: `reset_for_cheap_phase`
pone `cheap_started_at` nuevo pero **no limpia `cheap_finished_at`**, así que fin − inicio sale
negativo hasta que la fase termina. Cosmético, pero un número negativo en un informe de tiempos
despista. Limpiar los cuatro sellos al resetear.

## 45. La medida del 4.4-H sobre el post 5 (2026-08-26): el mecanismo funcionó, el resultado NO

**Este es el dato que cierra el ciclo de voces, y hay que mirarlo de frente.** David relanzó
«Transcripción y voces» sin rellenar nada, como pedía tu README. El registro muestra tu pase
funcionando EXACTAMENTE como lo diseñaste:

```
00:56  Diarización con pista de voces: ninguna (automático)     ← 1ª pasada, sin dato
01:29  Voces fantasma absorbidas: SPEAKER_02 (12.8 s)           ← red del 4.4-G ✔
01:29  Post 5: separación desequilibrada; segunda pasada con num_speakers=2
01:29  Diarización con pista de voces: {'num_speakers': 2}      ← red del 4.4-H ✔
```

Detectó el desequilibrio, repitió con el número exacto, y el cronómetro lo confirma
(`diarizar_s: 3959` ≈ dos pasadas). **El mecanismo entero, impecable.**

Y el resultado, medido en segundos de voz:

```
            23-ago    25-ago (4.4-G)   26-ago (4.4-H, 2ª pasada)
SPEAKER_00   90,7 %      91,9 %            95,7 %
SPEAKER_01    8,5 %       8,1 %             4,3 %
frases         748         404               255
```

**Forzar `num_speakers=2` sobre el vídeo COMPLETO dio un reparto PEOR que el automático.** Mi
experimento de docs/47 (84,8/15,2 con `num_speakers=2`) era sobre un tramo de 3 minutos con
diálogo denso; sobre los 22,8 minutos completos, el clustering asigna aún más al dominante.
Una lección de medición que asumo: **un experimento sobre un tramo no extrapola al vídeo
entero**, y lo escribo para que ninguno de los dos volvamos a caer.

### La conclusión honesta

**La vía de configuración de pyannote 3.1 está agotada.** Hemos probado automático, rango, y
número exacto: 91,9 / 91,9 / 95,7. Con estas dos voces concretas (dos hombres adultos, mismo
estudio, interjecciones cortas), el modelo de embeddings no separa mejor, se le diga lo que se
le diga. Los arreglos de post-proceso (suelo, fantasma, backchannels) SÍ funcionan y deben
quedarse; el problema restante es del embedding, no del cruce.

### Caminos que quedan (decisión de David, trabajo tuyo)

1. **Probar `pyannote/speaker-diarization-community-1`** (sucesor del 3.1, mismo mecanismo de
   token HF, sin coste de API). Es el candidato natural: mejor separación en voces parecidas.
   OJO a la matriz fijada del 4.1 (torch 2.2.2+cpu): verificar compatibilidad ANTES, y si exige
   subir torch, el candado del build (`import pyannote.audio`) cazará la ruptura.
2. **Aceptar el límite y compensar con la UI**: el reparto real de un explainer con un
   interlocutor que solo interjecta puede ser legítimamente 85/15; lo que es inaceptable es
   atribuirle frases. La heurística de backchannels ya recupera parte; podría reforzarse.
3. **Dejar de reintentar en frío**: la segunda pasada, visto esto, conviene que NO se dispare
   cuando la primera ya fue con `num_speakers` exacto (ya es así) NI repetirse en vídeos donde
   ya se midió que no mejora — quizá anotar en el Post que la segunda pasada no ganó nada, para
   no pagar 33 min de CPU en cada relanzamiento futuro del mismo vídeo.

**Nada de esto toca la línea roja de biometría**: cambiar de modelo de diarización sigue sin
almacenar huellas de voz (etiquetas por vídeo, como siempre).

## 46. Pase 4.4-I aplicado (2026-08-26) — addendum del operador

En producción (commit `dc7bf21`, **CI 290/290 verde a la primera, cero arreglos del operador**).
Informe en `docs/53`. Migración `analysis/0012` y los 3 ajustes en ambos entornos.

### Verificado

- **`keep_better_split` con los números reales del §45**: primera 8,1 % vs segunda 4,3 % →
  elige la primera. La corrección exacta que pedía el dato. Con esto la segunda pasada ya no
  puede empeorar: es la versión completa de «mirar el resultado» — mirar **los dos** y elegir.
- **El botón comunitario, en sus dos caras**: una etiqueta que no existe en el post
  (`SPEAKER_01` contra un post con `SPEAKER_1/2`) se rechaza en silencio con redirect — correcto,
  fail-closed; con la etiqueta válida resuelve, apaga `attribution_uncertain` y firma
  `resuelta por <usuario>` en la nota. Me tropecé yo mismo con la validación al probar con la
  etiqueta equivocada: quizá un `messages.error` («esa voz no existe en este vídeo») ahorraría
  la confusión a un moderador real, pero es cosmético.
- Panel: «Pasada de sentido» visible con Haiku de fábrica; `attribution_sense_pass=1`.

### Pendiente de validación real (lo hará David)

El supuesto que declaras — **la calidad de Haiku leyendo inglés hablado** — solo se mide
relanzando «Transcripción y voces» en el post 5. Cuando lo haga, contaré contra el volcado del
tramo 300-480 de `docs/52` y reportaré N/M/K y si conviene subir a Sonnet.

### Nota sobre el circuito

Con este pase, el tratamiento de voces queda en capas completas: oído (pyannote + pista),
autocorrección (2ª pasada solo-si-mejora), comprensión (pasada de sentido), y comunidad
(atribución incierta resuelta a mano). Es la arquitectura correcta: cada capa coge lo que la
anterior no pudo, y la última siempre es una persona.

## 47. Encargo 4.4-J: GPU de Runpod para todas las etapas pesadas (2026-08-26)

**Encargo completo en `docs/54`.** Resumen: David ordena diarización «estricta» usando la GPU
de Runpod, y lo mismo para el resto de etapas, con autorización permanente de gasto sobre su
saldo prepago (50 USD verificados por API). `RUNPOD_API_KEY` ya activa en producción
(`settings.RUNPOD_API_KEY`, commit `7eb0871`). Arquitectura pedida: **endpoint serverless** con
worker propio en `workers/gpu/` (imagen CUDA separada — la matriz torca del VPS NO se toca),
retorno a CPU con WARNING si falla, whisper **small → large-v3** (el mayor salto de calidad
disponible, impagable en CPU), y la 2ª pasada de voces pasa de 33 min a segundos — ahí puedes
probar community-1 sin el corsé de la matriz del 4.1. Reparto: tú el código (worker + cliente +
tests), el operador el endpoint y los `.env`. Coste estimado: 0,04-0,08 $/vídeo del saldo
Runpod, fuera de DailyBudget (mostrar informativo). Biometría: igual que hoy — nada persiste.

## 48. Aviso de alcance: la transcripción YA corre en GPU de Runpod (operador, 2026-08-26)

Como con el autocompletar de Wikidata: David ordenó que todo lo acelerable pasara por GPU y
esta pieza no podía esperar al pase. **Lo implementado** (commit `d9cc3c6`, CI 295/295):

- Endpoint serverless `istt-whisper` en la cuenta de David (imagen **oficial**
  `runpod/ai-api-faster-whisper:1.0.10`, A5000→4090, `workersMin=0`, `idleTimeout=5`).
- Cliente en `apps/agents/gpu.py`: opus mono 24k → base64 (tope 9,5 MB de carga útil de
  `/run`), sondeo de `/status`, y **cancelación del trabajo remoto si vence el timeout local**.
- Integración mínima en `_transcribe_first_tranche`: dos settings (`RUNPOD_WHISPER_ENDPOINT`,
  `WHISPER_GPU_MODEL=large-v3`) y retorno a CPU-small ante cualquier `None`.
- 5 tests (`OperadorGPUWhisper`), incluido el de cancelación por timeout.

**Dato de contrato que te ahorra una tarde**: en esa imagen, `word_timestamps=True` NO mete
las palabras en los segmentos — llegan en una **lista global aparte** (`output.word_timestamps`,
elementos `{word,start,end}`). `_map_output` las reparte por reloj con puntero. Medido contra
el endpoint real; la documentación no lo cuenta.

**Para tu 4.4-J** (sigue vigente, docs/54): queda TU parte — el worker GPU de **diarización**
(imagen a medida; no existe oficial). Reutiliza el patrón de `gpu.py` (mismo sondeo, misma
regla 5.7) y el endpoint te lo creo yo igual que este. Si tu pase quiere además subtítulos
mejores para vídeos >45 min (no caben en la carga útil), la solución limpia es que el worker
descargue el audio él mismo — apúntalo como decisión de diseño.

**Tiempos medidos en el disparo real**: arranque frío ~13 s + carga de modelo ~40 s + proceso.
Para el vídeo de 23 min esperamos 2-4 min de GPU (~2-4 céntimos). El modelo se carga POR
TRABAJO en esta imagen: si algún día duele, la alternativa es un worker propio con el modelo
residente — decisión de coste para David, no la tomes tú.

## 49. docs/56: la especificación GPU COMPLETA sustituye a docs/54 (operador, 2026-08-26)

Encargo de David: «todo lo necesario para que todas las tareas susceptibles de dar mejores y
más rápidos resultados se ejecuten por GPU». `docs/56` es tu documento de trabajo para el
4.4-J: inventario etapa a etapa (queda UNA pieza: el worker de diarización — el resto ya está
en GPU, no gana con GPU, o es API de Claude), contratos MEDIDOS contra el endpoint real,
estructura del worker, y las trampas ya pagadas (isServerless en templates, word_timestamps
global, cancelación por timeout). Léelo entero antes de escribir el pase.

## 50. Pase 4.4-J desplegado: la GPU entera funciona — y el mapa de minas de Runpod (operador, 2026-08-26)

**Tu pase era correcto: el handler funcionó a la primera en local.** Informe completo con las
SIETE trampas de plataforma en `docs/58` — léelo antes de tocar los workers. Las que te afectan
al diseñar:

1. **Contratos de pyannote 4 (medidos)**: torch ≥2.8; el audio DEBE entrar como
   `{'waveform': tensor, 'sample_rate': int}` (torchcodec está roto en los workers y tu aviso
   de io.py lo confirma); la salida es `DiarizeOutput` — el handler la desenvuelve por
   atributos (`speaker_diarization`, …) y así sirve para 3.x y 4.x a la vez.
2. **`OMP_NUM_THREADS=4` es VITAL**: sin él, `numpy.linalg.inv` del setup PLDA gira para
   siempre en los hosts de ~128 núcleos (cazado con faulthandler — que se queda en el handler:
   no lo quites). En el VPS jamás se manifestó: 8 núcleos.
3. **Los pools de GPU mienten** (AMPERE_24 sirvió Blackwell MIG) y **un release nuevo no
   recicla al worker caliente** — la palanca real es workersMax 0→1. Tope de ejecución: 15 min.
4. **La imagen vigente es `4.4-J-slim` (8,7 GB, base runtime torch 2.8, AMBOS modelos)**;
   la -devel de 21 GB tardaba >1 h en bajar en centros con enlace flojo. Las tres variantes
   conviven en ghcr; borra las gordas del repo si consolidas.
5. **Trampa BD cazada y cerrada (304 tests)**: `attribution_note` varchar(160) vs razón de
   Haiku sin acotar — el truncado se lee del campo (`_nota()` en attribution.py). Patrón a
   reutilizar: TODO texto de modelo que aterrice en un CharField pasa por un truncado así.
6. 📊 **Números del primer análisis real en GPU** (post 5): voces+2ª pasada 66→**3 min** (22×),
   fase completa 83→**29 min**, ~7 céntimos. `keep_better_split` eligió la 2ª pasada por MEJOR
   (5,9→8,6 %): tu corrección del 4.4-I actuando en la dirección buena. El cuello ahora es la
   DESCARGA del vídeo (~12 min) y la carga por-trabajo del modelo whisper (~40 s) — los dos
   pendientes de §5 de docs/58 son tuyos si David da luz verde.

## 51. EL FINAL DE LA HISTORIA DE LAS VOCES: community-1 en producción (operador, 2026-08-26)

La comparativa sobre el vídeo completo fue rotunda — 3.1: 91,4/8,6 (su techo de siempre);
**community-1: 78,4/21,6 a nivel de turnos**, mismo coste (22 s de GPU). Cambiado
`DIARIZE_GPU_MODEL` en el `.env` de producción y relanzado el post 5 con TODO el circuito
sano. **Resultado final: 67,3/32,7 · 0 fantasmas · 0 inciertas · 130 frases limpias** —
sense pass: 6 reetiquetadas, 6 partidas. La serie completa del post 5:
90,7/8,5 → 91,9/8,1 → 95,7/4,3 → 88,6/11,3 → **67,3/32,7**.

**Para tu próximo pase**: fija `DIARIZE_GPU_MODEL` default a community-1 en settings (hoy es
override de .env), y considera si la 2ª pasada sigue haciendo falta con community-1 (aquí
saltó 2,1→21,6: SÍ hizo falta — la 1ª de community-1 dejó una voz mínima; no la quites).
El candado del §45 queda superado por los hechos: la vía acústica NO estaba agotada — estaba
agotado el MODELO. Que David valide leyendo la transcripción; los números ya dicen que sí.

## 52. Parches 4.5-A/B/C (nuevo régimen: el operador desarrolla) — 2026-08-28

Informe completo en `docs/59`. Para el registro técnico del canal:
- **4.5-A**: `smooth_word_islands` recibe los turnos y NO reetiqueta una isla respaldada por
  un turno de su propio hablante (solape ≥50 %); `MAX_SENTENCE_SECONDS=30` corta la parrafada.
  Validado en el post 5: 76,8/23,1 (clava el 78/22 del oído), 0 frases >30 s. Patrón que deja:
  cuando una capa inferior mejora, revisar las heurísticas anti-ruido que nacieron de sus fallos.
- **4.5-B**: `ARG DENO_VERSION` 2.1.4→2.9.6 — el yt-dlp de 2026.08 declaraba el viejo
  `unsupported` y YouTube estrangulaba a 30 KB/s. Descarga real medida: 19,7 MB en 3,5 s.
  Lección de pin: los runtimes auxiliares también caducan; el síntoma vive en
  `[debug] JS runtimes:` del verbose.
- **4.5-C**: `catalog.AUDIO_ENGINES` + `audio_engine_for()` (panel > .env > default);
  `gpu.py` y el panel los consumen; sección nueva en `models.html` (+2 msgids al .po a mano).
  El barrido pasó a Sonnet por orden directa de David (dato de panel, no código).
- Pendiente gordo siguiente: worker propio de whisper con modelo residente (12,5→2-4 min).

## 53. Bloque 4.6 (A-F): la campaña del arranque — y la especificación del 4.7 (2026-08-29)

Informe completo con la serie del listón en `docs/60`. Técnica nueva que queda en el código:
**reescritura del arranque con candado de palabras sagradas + votación por mayoría de 3**
(`attribution.intro_rewrite`) — el patrón es reutilizable para cualquier corrección de texto
por modelo: N muestras, validación dura por muestra, voto por unidad.

**Techo medido**: los primeros ~7 s son indecidibles por texto (paridad cruzada sistemática
pese a nombre+cuota+ancla). **Especificación del 4.7 — la vía acústica de grano fino**: el
worker GPU de diarización debe devolver, además de `turns`, una pista de verificación por
tramo corto: similitud coseno de cada ventana (p. ej. 0,5 s) contra los centroides de las
voces DEL PROPIO VIDEO (embeddings efímeros en el worker, que muere tras el trabajo — NADA se
persiste: línea roja de biometría intacta). Con `scores: [[t0,t1,{S00:0.8,S01:0.2}],...]` en
la salida, el arranque se decide con física: la reescritura recibiría esos scores como ancla
POR PALABRA en vez de una cita única. pyannote expone los embeddings del pipeline; es tamaño
medio de worker + cliente. El listón (`eval_voces`) ya está listo para medirlo en minutos.

## 54. Bloque 4.7: AssemblyAI gana el duelo — 93% sustancial (2026-08-30)

Informe en `docs/61`. Registro técnico: motor en `apps/agents/assembly.py` (HTTP crudo, sin
SDK — cero dependencias nuevas; header `authorization` SIN Bearer; `speech_models` como array
con fallback; utterances en ms y letras → SPEAKER_NN por orden de aparición). Cadena en
`_transcribe_first_tranche` (primer eslabón) + rama `turns is None` en `run_cheap_phase`
(voces de fábrica → sin cruce). El liston es ahora un ALINEAMIENTO MONOTONO por DP
(`eval_voces` v4) — el casador codicioso con cursor era estructuralmente frágil y dio tres
falsos negativos de motor. Los 4.6-* (reescritura, votación, filtro de reacciones) SIGUEN
actuando sobre el material AAI y suman. El techo del §53 (verificación acústica de grano
fino en el worker GPU) queda ARCHIVADO: el motor conjunto lo disuelve; el worker GPU pasa a
red de seguridad.

## 55. Bloques 4.8-4.9: política científica + libro de cuentas (2026-08-30)

Informe en `docs/62`. Claves técnicas del canal: `InnocuousPhrase` (0013) y `CostEntry`
(0014) con `costs.py` (apunte thread-local del post en curso, validando existencia — el
fantasma de rollback reventaba FK dentro del peaje). `excise_embedded_reactions` opera sobre
las words del motor conjunto por FRASE COMPLETA con alineamiento fail-closed. **Trampa de
proveedor medida**: la doc de AssemblyAI describe `min/max_speakers_expected` y su API los
rechaza con 400 — solo `speakers_expected` existe de verdad; regla: contratos contra la API
VIVA, jamás contra el folleto (segunda vez: word_timestamps de Runpod). Topes con
degradación AAI→GPU→CPU y email→campana. El desglose por post es ACUMULADO adrede.
