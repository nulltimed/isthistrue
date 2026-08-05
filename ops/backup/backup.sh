#!/usr/bin/env bash
# Backups SIN VIM3 (decision de David: el VIM3 queda fuera del proyecto para siempre).
# restic cifrado sobre Google Drive via rclone + snapshots de IONOS como segunda linea.
# Requiere: rclone config (remoto "gdrive") y RESTIC_PASSWORD (guardada FUERA del servidor).
set -euo pipefail
REPO="rclone:gdrive:isthistrue-backups"
SRC="/opt/isthistrue"
restic -r "$REPO" backup "$SRC" --exclude "$SRC/media/audio_tmp" --exclude "$SRC/.git"
restic -r "$REPO" forget --keep-daily 7 --keep-weekly 3 --prune
