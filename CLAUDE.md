# CLAUDE.md — Instrucciones para Claude Código (operador de despliegue de David)

## Qué es este proyecto
isthistrue. / escierto. — plataforma social de fact-checking comunitario asistido por IA.
Django 5 + Celery + PostgreSQL16/pgvector + Redis + SearXNG + django-machina, en Docker.
**El documento canónico de decisiones es README.md: NUNCA contradecirlo. Las decisiones marcadas como congeladas NO se reabren.**

## Contexto del operador humano
David es autodidacta con conocimientos básicos. Explícale los errores con claridad y
metáforas si lo pide. La guía paso a paso para humanos es install.md; tú puedes
ejecutar sus pasos directamente.

## Infraestructura (NO ROMPER)
- VPS IONOS Ubuntu 24.04 (8 vCores, 16 GB). En el HOST corren Nginx, PostgreSQL,
  Postfix+Dovecot (correo personal de David), Grafana, Prometheus: **INTOCABLES**.
  Jamás pares, reconfigures o actualices esos servicios del host.
- El stack vive en Docker, solo loopback: producción **127.0.0.1:8090** (el 8080 lo ocupa ntfy, intocable), espejo 127.0.0.1:8081.
- Producción: /opt/isthistrue · Espejo: /opt/isthistrue-staging
- Operar SIEMPRE como usuario de servicio: `sudo -u i docker compose ...`
- Dominios: isthistrue / escierto / wikitrue / **stagings** (.xyztserver.com), registros A al VPS
  (David corrigió el DNS: stagings YA existe; "staging" queda como alias tolerado). Pendiente una vez:
  `sudo certbot --nginx -d stagings.xyztserver.com`.
- La app propia del foro tiene **label 'forum_local'** (el label 'forum' es de machina):
  makemigrations/migrate y referencias por string usan forum_local.
- Las migraciones están COMMITEADAS en el repo: genera las nuevas encima (0002, 0003...) y
  commitéalas; NUNCA regeneres ni borres las existentes (wiki/0001 lleva VectorExtension()).

## Comandos clave
- Producción: `cd /opt/isthistrue && sudo -u i docker compose up --build -d`
- Espejo (apagado por defecto): `cd /opt/isthistrue-staging && sudo -u i docker compose -f docker-compose.staging.yml -p staging up --build -d` (y `down` al terminar)
- Migraciones: `sudo -u i docker compose exec web python manage.py makemigrations accounts analysis wiki forum_local panel && sudo -u i docker compose exec web python manage.py migrate`
- Primera vez BD: `sudo -u i docker compose exec db psql -U isthistrue -c "CREATE EXTENSION IF NOT EXISTS vector;"` y luego `seed_settings` + `seed_forum` + `createsuperuser` + `collectstatic --noinput`
- Tests: `sudo -u i docker compose exec web python manage.py test tests --settings=tests.settings_test`

## Ritual de despliegue OBLIGATORIO
1. Commit y push a `nulltimed/isthistrue` (main). Espera el CI de GitHub Actions.
2. CI en rojo: NO desplegar. Diagnostica o informa a David con el enlace del fallo.
3. CI en verde: actualizar y encender el ESPEJO, migrar, pasar el checklist
   (docs/04-checklist-verificacion.md + Parte D del install.md).
4. Solo si el espejo pasa: apagar espejo y desplegar a producción
   (down → .bak con fecha → git pull → up --build → migrate → collectstatic).

## Líneas rojas (NUNCA)
- NUNCA commitear ni imprimir `.env` (contiene secretos). Verificar `.gitignore` antes de todo push.
- NUNCA tocar el mail del host, sus puertos o su DNS (elviajedeunlouco.es).
- NUNCA proponer ni reintroducir Telegram (descartado PARA SIEMPRE por David).
- NUNCA almacenar multimedia de terceros ni huellas de voz (biometría prohibida salvo
  visto bueno escrito del abogado de David — no construido).
- NUNCA exponer el domicilio real de David (aviso legal: apartado de correos pendiente).
- NUNCA subir los límites de gasto (DAILY_BUDGET_EUR / MONTHLY_CAP_EUR) sin orden explícita de David.
- El espejo SIEMPRE con MOCK_AGENTS=true (jamás gasta presupuesto de API).
- Backdoors: cero. El SSH de administrador de David se conserva; el usuario `i` no tiene shell.

## Protocolo para ZIPs de la IA de desarrollo (Fable)
Los ZIP se aplican SOBRE el árbol git, nunca como sustitución ciega:
1. Descomprimir en un directorio temporal y sincronizar archivos sobre el working tree
   (rsync sin --delete), EXCLUYENDO apps/*/migrations/ (las commiteadas mandan).
2. `git diff` y revisar que no se pierden los fixes de main (labels, related_name, puerto 8090...).
3. `makemigrations` para los modelos nuevos → commitear las migraciones resultantes.
4. Tests (`--settings=tests.settings_test --noinput`) → ritual normal (espejo → producción).
5. Tras migrar en cada entorno: `manage.py ensure_superuser` (lee ADMIN_EMAIL/ADMIN_PASSWORD del .env).

## Lecciones de operacion acumuladas
- En YAML los comentarios van FUERA de las comillas (bug del ZIP Fase 3, arreglado).
- Con DEBUG=False, /static/ lo sirve WhiteNoise (middleware): tras cada build, `collectstatic --noinput`.
- /media/ lo sirve la app con candado: code_batches/ SOLO staff.
- El gasto simulado del mock en DailyBudget es INTENCIONAL (prueba banner y candados sin coste real).
- Superusuario: SIEMPRE `ensure_superuser` (lee .env), nunca createsuperuser.
- **El Khadas VIM3 esta FUERA del proyecto para siempre** (decision de David): no nombrarlo,
  no usarlo, no proponerlo. Backups = restic sobre rclone:gdrive + snapshots IONOS.

- Reparto de modelos v2: Haiku SOLO barrido; resto Sonnet; Opus reescanea posts >40% votos
  (suelo 10, una vez). MODERATION_TRIAGE_MODEL revertible en .env si la factura de moderacion duele.

- Reparto de modelos (README §25): clasificador=Sonnet, veredictos=Sonnet, moderacion=SOLO
  Haiku, reescaneo 40%=Opus. Nueva migracion pendiente al aplicar: analysis (opus_rescanned).

## CANDADO DE ESTÁTICOS (2026-08-13 — cumplir SIEMPRE)
**Ningún despliegue está terminado sin el smoke-test de estáticos en verde**, en cada dominio:
`curl -s -o /dev/null -w "CSS: %{http_code} %{size_download} bytes\n" https://<dominio>/static/css/main.css`
y `curl -s https://<dominio>/ | grep -c masthead`. Éxito: CSS=200 con >5 KB y masthead ≥1.
Si falla: `collectstatic --noinput` + `restart web` y repetir. Adjuntar el resultado al informe.
Un despliegue "funcional pero feo" es un despliegue ROTO a ojos del usuario.
(Defensa estructural: el command del web ejecuta collectstatic en cada arranque, porque
/app/staticfiles vive en el fs del contenedor y cualquier recreación lo vacía.)

## Al terminar cualquier tarea
Informa a David de qué se hizo, qué falló (logs literales) y el estado del CI/espejo/producción.
**Y actualiza el handoff (`docs/21-handoff-operador-claude-code.md`) en CADA iteración de
despliegue** (orden de David, 2026-08-15): fecha y commit de cabecera, sección §10 "Estado
EXACTO" y cualquier regla/trampa nueva de la iteración. Se commitea y sube a GitHub junto
con el informe del pase. El handoff debe permitir SIEMPRE que otra instancia de Claude Code
continúe el trabajo sin explicaciones adicionales.
