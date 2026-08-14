#!/usr/bin/env bash
# Backups isthistrue (calendario de David): snapshot DIARIO 00:00 -> carpeta "isthistrue"
# en la RAIZ de su Google Drive (remoto rclone: "isthistrue"). Retencion 7 diarias +
# 3 semanales. Lunes: verificacion de integridad. Contraseña en /root/.restic-pass (600).
set -euo pipefail
export RESTIC_PASSWORD_FILE=/root/.restic-pass
REPO="rclone:isthistrue:isthistrue"
SRC="/opt/isthistrue"
restic -r "$REPO" backup "$SRC" --exclude "$SRC/media/audio_tmp" --exclude "$SRC/.git"
restic -r "$REPO" forget --keep-daily 7 --keep-weekly 3 --prune
if [ "$(date +%u)" = "1" ]; then
    restic -r "$REPO" check
fi
