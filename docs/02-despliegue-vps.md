# Despliegue en el VPS IONOS (resumen; NO romper lo que ya corre en el host)
1. Usuario de servicio: `sudo useradd -r -s /usr/sbin/nologin -G docker i`. Se opera SIEMPRE con `sudo -u i docker compose ...`. Tu SSH de administrador SE CONSERVA; backdoors: cero.
2. Código en `/opt/isthistrue` (propietario `i`). `.env` con permisos 600.
3. DNS IONOS: 3 registros A → IP del VPS: isthistrue, escierto, wikitrue.
4. Nginx del host: copiar `nginx/isthistrue-host.conf` a sites-available, enlazar, `nginx -t`, reload. Luego `certbot --nginx` con los 3 dominios. Página de pánico en `/var/www/isthistrue-panic/panic.html`.
5. Backups: carpeta NUEVA en el VIM3 `/mnt/server/backups/isthistrue` (renombrada, crearla). `ops/backup/backup.sh` en cron 5:00; RESTIC_PASSWORD fuera del servidor. Test de restauración mensual.
6. ufw: solo 22/80/443. fail2ban activo.
