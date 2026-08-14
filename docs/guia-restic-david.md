# TU GUÍA DE BACKUPS Y RECUPERACIÓN — restic (guárdala junto a la contraseña)

## Qué tienes montado
Cada noche a las 00:00, el notario (restic) fotografía TODO el proyecto (/opt/isthistrue),
cifra la foto y la guarda en la carpeta **isthistrue** de la raíz de tu Google Drive.
Guarda las últimas **7 fotos diarias + 3 semanales**. Los lunes revisa el trastero entero
por si alguna caja se corrompió. Tu contraseña vive en /root/.restic-pass del VPS — y en tu
Bitwarden y en un papel. **Si se pierde la contraseña, TODO es ilegible para siempre.**

⚠ Lo que verás si abres la carpeta en Drive: cajas cifradas con nombres raros (data,
snapshots...). ES NORMAL: el catálogo legible por fechas no está en Drive, está en el notario:

## Ver tus copias ORDENADAS POR FECHA (cuando quieras)
```
sudo RESTIC_PASSWORD_FILE=/root/.restic-pass restic -r rclone:isthistrue:isthistrue snapshots
```
Salida: una tabla con ID, fecha y hora de cada copia, en orden cronológico. Ese ID corto
(p. ej. `4f2a91bc`) es "la foto de ese día".

## Simulacro mensual (día 1 de cada mes — 2 minutos; una copia no probada es una esperanza)
```
sudo RESTIC_PASSWORD_FILE=/root/.restic-pass restic -r rclone:isthistrue:isthistrue restore latest --target /tmp/tr
ls /tmp/tr/opt/isthistrue        # debe listar el proyecto
sudo rm -rf /tmp/tr
```

## Ver el diario del notario
```
cat /var/log/isthistrue-backup.log
```

## ☠ EL DÍA DEL DESASTRE — recuperación completa desde cero, paso a paso
Escenario: el VPS ha muerto (disco roto, hackeo, borrado). Tienes: tu cuenta de Google,
tu contraseña restic (Bitwarden/papel) y esta guía. Tiempo estimado: 1-2 horas.
1. **Servidor nuevo**: contrata/reinstala un VPS Ubuntu (IONOS te restaura o creas otro).
   Entra por SSH como root o con sudo.
2. **Herramientas**: `sudo apt update && sudo apt install -y restic rclone docker.io docker-compose-v2`
3. **Reconectar tu Drive**: `sudo rclone config` → n → nombre: `isthistrue` → tipo: drive →
   Enter a todo → autoriza con tu Google (si el servidor no tiene navegador: responde "n" a
   "use web browser" y sigue la opción de `rclone authorize "drive"` desde tu Windows, como
   hiciste la primera vez). Comprueba: `sudo rclone lsd isthistrue:` debe listar la carpeta.
4. **La llave**: `sudo bash -c 'read -rs -p "Contraseña: " P && printf "%s" "$P" > /root/.restic-pass && echo'`
   y `sudo chmod 600 /root/.restic-pass`
5. **Traerlo todo de vuelta** (la última foto, o cambia `latest` por el ID de otra fecha):
```
sudo RESTIC_PASSWORD_FILE=/root/.restic-pass restic -r rclone:isthistrue:isthistrue restore latest --target /
```
   Esto recoloca /opt/isthistrue entero: código, base de datos, .env, media. 
6. **Volver a la vida**: recrear el usuario de servicio si no existe
   (`sudo useradd -r -s /usr/sbin/nologin i && sudo usermod -aG docker i`,
   `sudo chown -R i:i /opt/isthistrue`) y arrancar:
   `cd /opt/isthistrue && sudo -u i docker compose up --build -d`
7. **DNS y puerta**: si la IP del VPS nuevo es DISTINTA, actualiza en IONOS los registros A
   (isthistrue, escierto, wikitrue, stagings) a la IP nueva; instala nginx+certbot del host
   siguiendo install.md B7-B8. Si restauraste el mismo VPS con la misma IP, nada que tocar.
8. **Comprobar**: la web responde, entras como `d`, y `restic snapshots` sigue viendo el
   historial. Reinstala el cron (línea del despertador, en la tarea de backups).

## Segunda línea independiente
Los **snapshots de IONOS** de tu panel fotografían el disco entero por otra vía. Si Google o
la contraseña fallaran, restaura el snapshot de IONOS desde su panel (botón "Restaurar").
Dos sistemas, dos caminos: cinturón y tirantes.
