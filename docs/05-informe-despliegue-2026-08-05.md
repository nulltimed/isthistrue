# Informe de despliegue — 2026-08-05 (primer despliegue en el VPS)

> Operador: Claude Código. Todo lo de abajo está hecho y verificado salvo lo marcado **PENDIENTE DAVID**.

## Resultado en una línea

**isthistrue está EN PRODUCCIÓN**: https://isthistrue.xyztserver.com · https://escierto.xyztserver.com · https://wikitrue.xyztserver.com (HTTPS con Let's Encrypt, HTTP redirige). Tests 10/10 OK. Espejo ensayado y apagado. El correo, Bitwarden, Joplin, Grafana y demás servicios del host quedaron intactos.

## Qué se hizo, por orden

1. **Parte 0 (GitHub)**: repo `nulltimed/isthistrue` poblado en `main` (8 commits). ⚠️ El CI **no pudo subirse**: el token classic solo tiene scope `repo` y GitHub exige `workflow` para crear `.github/workflows/ci.yml`. Como portero sustituto, la suite de tests se ejecutó en el propio VPS (verde).
2. **Usuario de servicio** `i` creado (nologin, sin SSH, grupo docker). Clon en `/opt/isthistrue`.
3. **`.env` de producción**: `DEBUG=False`, `SECRET_KEY` y `POSTGRES_PASSWORD` generados aleatorios (archivo con permisos 600, dueño `i`; no impreso en ningún sitio).
4. **Stack levantado** (`sudo -u i docker compose up --build -d`): web (gunicorn), worker, beat, db (pgvector/pg16), redis, searxng. Solo loopback.
5. **BD**: extensión `vector`, migraciones (propias + machina + otp), `seed_settings`, `seed_forum`, superusuario `d`, `collectstatic` (198 archivos).
6. **Tests** (robot ITV): **10/10 OK** tras 2 arreglos de código (ver §Errores).
7. **Espejo** (`/opt/isthistrue-staging`, puerto 8081, `STAGING_MODE=true`, MOCK forzado): encendido, migrado, sembrado y **checklist automatizable superado**; después apagado (C3). Verificado en el espejo: portada/login/registro/búsqueda/RSS/metrics/legales/panel/foro (200), candado de invitados (redirige a login), análisis simulado completo (submit → PENDING_VALIDATION → voto de mod → DONE → 2 claims verdes [SIMULADO] en la wiki), tarjeta compartible PNG, etiquetas SPEAKER_1/2 + "¿Quién habla?", voto de nombre confirmado en solitario por el mod, banner "Hoy: 0,00/2,00 €".
8. **Nginx del host**: `isthistrue.conf` instalado, `nginx -t` OK, reload sin tocar los demás sitios. Página de pánico en `/var/www/isthistrue-panic/panic.html`. **Certbot** emitió certificado para los 3 dominios con redirección a HTTPS.
9. **fail2ban**: estaba desinstalado (quedaba solo config residual); reinstalado y activo según install.md B9. *Si lo habías quitado a propósito, dímelo y lo dejo como estaba.* **ufw no se tocó** (ya estaba activo con 80/443/22222; el paso "ufw allow OpenSSH" del manual se omitió adrede porque tu SSH va por el 22222).

## Desviaciones respecto al plan (documentadas y commiteadas)

| Qué | Por qué | Dónde quedó |
|---|---|---|
| Puerto producción **8090** (no 8080) | El 8080 del loopback lo ocupa **ntfy** (servicio del host, intocable) | docker-compose.yml, nginx conf, README §13, CLAUDE.md, install.md, checklist |
| Alias `staging.xyztserver.com` en el espejo | El registro A real es **staging**; ni `stagings` (lo cableado) ni `stagins` (la errata que temía el README §22) existen en DNS | nginx conf + docker-compose.staging.yml |
| Migraciones commiteadas al repo | Se generaban dentro del contenedor y se perdían en cada rebuild; commiteadas son reproducibles (el `makemigrations` del CI pasará a "No changes detected") | apps/*/migrations/ |

## Errores de código encontrados y ARREGLADOS (commits en main)

1. **`Application labels aren't unique: forum`** — `apps.forum` chocaba con `machina.apps.forum`; la web no arrancaba (crashloop). Arreglo: `label = 'forum_local'` en `apps/forum/apps.py` (y los comandos `makemigrations` de los 4 documentos actualizados). Commit `8950236`.
2. **`ModuleNotFoundError: machina.app`** — `config/urls.py` usaba la API vieja de machina (`machina.app.board`); retirada en machina 1.x. Arreglo: `include(machina_urls)`. Commit `211eefe`.
3. **E304/E305 `related_name='posts'`** — `analysis.Post.author` chocaba con el `posts` de machina. Arreglo: `related_name='analysis_posts'`. Commit `15d16cb`.
4. **`type "vector" does not exist` en tests** — la BD de test se crea de cero sin la extensión. Arreglo: `VectorExtension()` como primera operación de `wiki.0001` (vale para el CI futuro también). Commit `a5e7656`.
5. **2 tests de votaciones caían con `kombu ConnectionError` (amqp)** — `config/__init__.py` estaba vacío: los `@shared_task` usaban la app Celery por defecto (broker amqp inexistente) en vez de la configurada (Redis + eager en tests). Arreglo: import canónico `from .celery import app as celery_app`. Commit `f4bc829`. *Este bug también afectaba a producción vía web (cualquier `.delay()` desde una vista gunicorn habría fallado).*

## Warnings observados (no bloqueantes)

- Build pip: "Running pip as the 'root' user" (normal dentro de Docker).
- Celery worker: `SecurityWarning: running the worker with superuser privileges` (contenedor; mejorable con user no-root en el Dockerfile) y `CPendingDeprecationWarning: broker_connection_retry` (celery 5.4, inofensivo).
- nginx -t: warnings preexistentes de otros sitios del host (ssl_stapling de actualbudget/bitwarden/etc. y protocol options de grafana). No los introduje yo y no los toqué.
- Primer intento de tests se colgó por una BD `test_isthistrue` huérfana; se borró y ahora se usa `--noinput`.

## PENDIENTE DAVID (en orden de importancia)

1. **Token GitHub con scope `workflow`** (Settings → Developer settings → Tokens classic → scopes `repo` + `workflow`) para poder subir el CI. El archivo está listo en el VPS (`/tmp/ci.yml.pendiente` y en el árbol local del workspace).
2. **Claves del `.env` de producción** (`sudo nano /opt/isthistrue/.env` como root, o pídemelo): `ANTHROPIC_API_KEY` (y entonces `MOCK_AGENTS=false`), `TURNSTILE_SITE_KEY/SECRET_KEY`, `EMAIL_HOST_USER/PASSWORD` (Brevo), `HF_TOKEN` (diarización, Parte D1). Tras cambiar: `cd /opt/isthistrue && sudo -u i docker compose restart web worker beat`. **Ahora mismo el sitio está en modo simulado ([SIMULADO], sin gasto).**
3. **DNS del espejo**: decide — renombrar el registro A `staging` → `stagings` (lo congelado) o bendecir `staging` (ya funciona como alias). Después: `sudo certbot --nginx -d <el-que-sea>.xyztserver.com`.
4. **Contraseñas del superusuario `d`** (producción y espejo): te las paso por el chat; cámbialas en /admin/ → Users.
5. **Permisos del foro machina** (roce esperado, checklist paso 5): entra en `/admin/` → Forum permissions y concede leer/responder al grupo por defecto en Principal y Off-Topic.
6. **Checklist manual restante**: registro con Turnstile real, emails Brevo, amistad entre 2 cuentas, markdown/escape en foro, OG cards, reclamación DSA de punta a punta, autoborrado RGPD, campo del apartado de correos en el aviso legal.
7. **Backups B10**: requieren el VIM3 por VPN (crear `/mnt/server/backups/isthistrue`), elegir RESTIC_PASSWORD (guárdala FUERA del servidor) y el asistente interactivo de rclone para Google Drive. No lo pude hacer sin ti.
8. **fail2ban**: confirma que quieres tenerlo activo (estaba desinstalado).

## Estado final

- **Producción**: 6 contenedores Up, HTTPS en los 3 dominios, HTTP 200, logs limpios.
- **Espejo**: preparado y APAGADO (como debe estar).
- **GitHub**: `main` = código del VPS (sincronizado; único fichero fuera: `ci.yml` por el scope del token).
- **CI**: no existe aún en GitHub (ver PENDIENTE 1); portero sustituto: tests en el VPS, verdes.
