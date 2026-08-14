# Informe — BACKUPS ACTIVADOS (2026-08-14, 03:1x de la madrugada)

> Tarea: tarea-backups-claude-code.md (versión definitiva, password-file). Ejecutada completa.
> La contraseña la tecleó David directamente en su SSH a /root/.restic-pass (600, root):
> el operador NO la vio y NO está registrada en ningún log, informe ni historial.

## Resultado en una línea

**El proyecto tiene por fin copias de seguridad reales, cifradas, diarias y PROBADAS** en la
carpeta `isthistrue` de tu Google Drive — incluida la base de datos, que el diseño original
NO copiaba (hallazgo crítico del operador, arreglado sobre la marcha).

## El hallazgo crítico: la BD no viajaba en el backup

El `backup.sh` copiaba `/opt/isthistrue`… pero **la base de datos vive en el volumen Docker
`pgdata`, fuera de esa ruta**: usuarios, posts, claims, donaciones y códigos NO estaban en la
copia. En un desastre habrías recuperado el código (que ya está en GitHub) y perdido los datos
(lo único irreemplazable). Arreglo aplicado y commiteado: el script ahora hace `pg_dump` de la
BD comprimido a `ops/backup/db-dump.sql.gz` ANTES de cada snapshot (58 tablas verificadas
dentro del depósito). Restauración completa = restaurar snapshot + `zcat db-dump.sql.gz | psql`.

## Verificaciones del §5 (todas ejecutadas, salida real)

1. **`rclone lsd isthistrue:`** → carpeta `isthistrue` presente (creada 03:10), 10 objetos,
   421 KiB cifrados.
2. **Snapshots** → 2 listados (`b2453574` inicial y `dab5c701` ya con la BD); retención
   7 diarias + 3 semanales aplicada por el script en cada ejecución.
3. **Prueba de restauración REAL** (×2): `restore latest` → 221 archivos; `manage.py` y
   `settings.py` restaurados **idénticos byte a byte** a los originales (cmp); `.env` incluido
   (imprescindible para levantar de cero); volcado de BD restaurado con sus 58 tablas. Temporales limpiados.
4. **Cron instalado**: `0 0 * * * /opt/isthistrue/ops/backup/backup.sh >> /var/log/isthistrue-backup.log 2>&1`
   (crontab de root; SIN contraseña en el crontab — la lee de /root/.restic-pass). Los lunes el
   propio script añade `restic check` de integridad.
5. **Mañana**: mira `/var/log/isthistrue-backup.log` tras las 00:00 — debe registrar la primera
   ejecución automática. Y el día 1 de cada mes: repetir la prueba de restauración
   (guia-restic-david.md, ya en docs/). "Una copia no probada es una esperanza."

## Detalles técnicos

- restic 0.16.4 · remoto rclone `isthistrue` → carpeta `isthistrue` en la raíz del Drive.
- Depósito cifrado: sin `/root/.restic-pass` (o tu copia en Bitwarden/papel) los datos son
  IRRECUPERABLES — ese es el diseño.
- Exclusiones: `media/audio_tmp` y `.git` (el código vive en GitHub).
- `db-dump.sql.gz` añadido al `.gitignore` (es un artefacto local, no código).
- Segunda línea de defensa: snapshots de IONOS ya contratados, por su cuenta.

## Los 3 semáforos del plan de cierre — TODOS EN VERDE por fin

DNS ✅ · Brevo ✅ (emails reales verificados en el pase 3.7) · **Backups ✅ (hoy)**.
