# Informe — Pase 3.6 + preparación de backups (2026-08-05, sesión de cierre)

> Operador: Claude Código. Según plan-sesion-cierre.md. Run verde: https://github.com/nulltimed/isthistrue/actions/runs/31045661826

## Resultado en una línea

**Pase 3.6 EN PRODUCCIÓN en los 3 dominios** (isthistrue incluido: tu arreglo del DNS funciona) y **backups listos al 95%** — solo falta que David teclee su RESTIC_PASSWORD (bloque de comandos abajo).

## Pase 3.6 (ritual canónico completo)

- Banner XL con el **botón real de suscripción de PayPal** (tu client-id) en todas las páginas; "Más opciones" → /donaciones/ con Patrono + donación puntual, **una sola carga del SDK** (la de base.html).
- **Logo a 96px** escritorio / 56px móvil, centrado.
- `cookies.html` ampliado: declara la carga del SDK de PayPal en toda la web.
- `donation_goal_eur=100` (seed por defecto + update directo en BDs de espejo y producción).

### Checklist 59-63

- **59.** ✔ SDK cargado 1 vez + contenedor del botón presente en portada (espejo y los 3 dominios de producción). *No se completó ninguna suscripción, como pedía la guía.*
- **60.** ✔ CSS sirve `height:96px` para el logo (verificado en el CSS publicado). **Falta tu ojo**: Ctrl+Shift+R y confirma que lo ves como lo describiste; si no, captura.
- **61.** ✔ /donaciones/ con una única carga del SDK (sin doble carga → sin errores JS de duplicado).
- **62.** ✔ cookies.html menciona PayPal (6 veces).
- **63.** ✔ `logo-es.svg` → 200 `image/svg+xml`.
- Tests 21/21 y logs limpios en producción.

## Backups — TODO preparado; te toca solo la contraseña

**Estado verificado**: restic 0.16.4 instalado · remoto rclone `isthistrue:` funciona (lista tu Drive) · la carpeta `isthistrue` del Drive no existe aún (la creará el init: eso era tu "problema", no había nada roto) · `backup.sh` nuevo con `REPO="rclone:isthistrue:isthistrue"` commiteado y en `/opt/isthistrue/ops/backup/backup.sh` (ejecutable, sintaxis validada) · calendario: diaria 00:00, retención 7 diarias + 3 semanales, lunes `restic check`.

**Tu parte (5 minutos, por SSH). Antes: inventa la RESTIC_PASSWORD (sin espacios ni comillas), guárdala en Bitwarden + papel. Sin ella los backups son IRRECUPERABLES.**

```bash
# 1) Teclea la contraseña UNA vez (no se muestra ni queda en el historial):
read -rsp 'RESTIC_PASSWORD: ' RESTIC_PASSWORD; echo; export RESTIC_PASSWORD

# 2) Crear el depósito cifrado en tu Drive:
sudo RESTIC_PASSWORD="$RESTIC_PASSWORD" restic -r rclone:isthistrue:isthistrue init

# 3) Primer backup + comprobar que existe:
sudo RESTIC_PASSWORD="$RESTIC_PASSWORD" /opt/isthistrue/ops/backup/backup.sh
sudo RESTIC_PASSWORD="$RESTIC_PASSWORD" restic -r rclone:isthistrue:isthistrue snapshots

# 4) Prueba de restauración ("una copia no probada es una esperanza"):
sudo RESTIC_PASSWORD="$RESTIC_PASSWORD" restic -r rclone:isthistrue:isthistrue restore latest --target /tmp/tr && ls /tmp/tr/opt/isthistrue | head && sudo rm -rf /tmp/tr

# 5) Programar la diaria de las 00:00 (única copia de la contraseña: crontab de root, permiso 600):
sudo env RESTIC_PASSWORD="$RESTIC_PASSWORD" bash -c '(crontab -l 2>/dev/null | grep -v isthistrue-backup; echo "0 0 * * * RESTIC_PASSWORD=$RESTIC_PASSWORD /opt/isthistrue/ops/backup/backup.sh >> /var/log/isthistrue-backup.log 2>&1") | crontab -'

# 6) Limpieza de la variable de tu sesión:
unset RESTIC_PASSWORD
```

**Mañana**: mira `/var/log/isthistrue-backup.log` — debe tener la ejecución de las 00:00. Y el día 1 de cada mes, repite el paso 4 (test de restauración mensual).

## Estado final de la sesión

- **Producción**: commit del pase 3.6 en los 3 dominios, HTTPS, logs limpios. DNS de isthistrue restaurado ✔ (verificado sirviendo la web).
- **Espejo**: mismo commit, APAGADO.
- **GitHub** = VPS = espejo; CI verde.
- **Semáforos del plan de cierre**: DNS ✅ · Pase 3.6 ✅ · Backups ⏳ (a un teclado de distancia) · Brevo ⏳ (tu "llegaron" pendiente, con guia-cerrar-brevo.md).
