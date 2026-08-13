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
