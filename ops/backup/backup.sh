#!/usr/bin/env bash
# Backups isthistrue (calendario de David): snapshot DIARIO 00:00 -> carpeta "isthistrue"
# en la RAIZ de su Google Drive (remoto rclone: "isthistrue"). Retencion 7 diarias +
# 3 semanales. Lunes: verificacion de integridad. Contraseña en /root/.restic-pass (600).
set -euo pipefail
export RESTIC_PASSWORD_FILE=/root/.restic-pass
REPO="rclone:isthistrue:isthistrue"
SRC="/opt/isthistrue"
# CRITICO (hallazgo del operador 2026-08-14): la BD vive en el volumen Docker pgdata,
# FUERA de /opt/isthistrue — sin este volcado el backup no llevaba los datos.
docker compose --project-directory "$SRC" exec -T db pg_dump -U isthistrue isthistrue \
    | gzip > "$SRC/ops/backup/db-dump.sql.gz"
restic -r "$REPO" backup "$SRC" --exclude "$SRC/media/audio_tmp" --exclude "$SRC/.git"
restic -r "$REPO" forget --keep-daily 7 --keep-weekly 3 --prune
if [ "$(date +%u)" = "1" ]; then
    restic -r "$REPO" check
fi
