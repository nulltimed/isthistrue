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
- El stack vive en Docker, solo loopback: producción 127.0.0.1:8090, espejo 127.0.0.1:8081.
- Producción: /opt/isthistrue · Espejo: /opt/isthistrue-staging
- Operar SIEMPRE como usuario de servicio: `sudo -u i docker compose ...`
- Dominios: isthistrue / escierto / wikitrue / stagings (.xyztserver.com), registros A al VPS.

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

## Al terminar cualquier tarea
Informa a David de qué se hizo, qué falló (logs literales) y el estado del CI/espejo/producción.
