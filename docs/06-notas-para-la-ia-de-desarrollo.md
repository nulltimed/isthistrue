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
