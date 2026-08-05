# Instalación en el EliteBook (WSL2 + Docker Desktop) — resumen
Si ya montaste WSL2 y Docker Desktop para el Hito 1, salta directamente al checklist 04.
1. PowerShell como administrador: `wsl --install -d Ubuntu` → reiniciar → crear usuario Linux.
2. Instalar Docker Desktop para Windows; en Settings → Resources → WSL Integration, activar Ubuntu.
3. Abrir Ubuntu (terminal WSL): `docker --version` y `docker compose version` deben responder.
4. Seguir el checklist `04-checklist-verificacion.md` paso a paso y reportar TODO al terminar.
