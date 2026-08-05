#!/usr/bin/env bash
# restic cifrado, mismo repo, 3 destinos. RESTIC_PASSWORD fuera del servidor.
# Destinos: VIM3 sftp/VPN (/mnt/server/backups/isthistrue), GDrive via rclone, snapshots IONOS.
set -euo pipefail
REPO_VIM3="sftp:vim3:/mnt/server/backups/isthistrue"
SRC="/opt/isthistrue"
restic -r "$REPO_VIM3" backup "$SRC" --exclude "$SRC/media/audio_tmp"
rclone sync "$REPO_VIM3" gdrive:isthistrue-backups || true
restic -r "$REPO_VIM3" forget --keep-daily 7 --keep-weekly 3 --prune
