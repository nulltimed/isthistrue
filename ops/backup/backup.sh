#!/usr/bin/env bash
# Backups (calendario de David): snapshot DIARIO a las 00:00; retencion 7 diarias +
# 3 semanales ("3 copias totales"); los LUNES ademas verificacion de integridad.
# Remoto rclone de David: "isthistrue" -> carpeta isthistrue en la raiz de su Google Drive.
set -euo pipefail
REPO="rclone:isthistrue:isthistrue"
SRC="/opt/isthistrue"
restic -r "$REPO" backup "$SRC" --exclude "$SRC/media/audio_tmp" --exclude "$SRC/.git"
restic -r "$REPO" forget --keep-daily 7 --keep-weekly 3 --prune
if [ "$(date +%u)" = "1" ]; then
    restic -r "$REPO" check   # lunes: integridad del deposito completo
fi
