# GUÍAS PARA DAVID — Brevo · PayPal.me · Backups · fail2ban (con metáforas)

## 1. BREVO — tu oficina de correos profesional
**Metáfora completa**: hasta ahora tu web escribe cartas pero no tiene oficina de correos: las
"envía" a un cajón (los logs). Brevo es una oficina de correos profesional con buena reputación:
los carteros de Gmail y Outlook la conocen y no tiran sus cartas al spam. Lo que vas a hacer:
abrir cuenta en esa oficina, demostrar que el remitente "xyztserver.com" es tuyo (el sello DKIM),
y darle a tu web la llave del buzón de salida.

**Paso a paso:**
1. Entra en **brevo.com** → "Sign up free" → usa `david@xyztserver.com` y una contraseña nueva
   → confirma el email que te llega → en el formulario de bienvenida di que eres particular/proyecto
   pequeño (no afecta a nada).
2. Menú izquierdo (o tu avatar) → **Senders, Domains & Dedicated IPs** → pestaña **Domains**
   → **Add a domain** → escribe `xyztserver.com`.
3. Brevo te muestra **2-3 registros DNS** (el "sello de autenticidad"). Son del tipo TXT, con
   nombres como `mail._domainkey.xyztserver.com` y valores larguísimos. Déjalos a la vista.
4. En OTRA pestaña: panel de **IONOS** → tu dominio xyztserver.com → DNS → **Añadir registro**
   → tipo TXT → copia nombre y valor EXACTOS de cada registro de Brevo. ⚠ Solo AÑADES:
   no toques ni borres nada de lo que ya hay (tu correo personal vive en ese panel).
   Truco IONOS: si Brevo da el nombre completo `mail._domainkey.xyztserver.com`, en IONOS
   a veces basta poner `mail._domainkey` (el dominio lo añade solo).
5. Espera 10-60 minutos (el sello tarda en "secarse" = propagación DNS) → vuelve a Brevo →
   botón **Verify** hasta que todo salga en verde.
6. Menú **SMTP & API** → pestaña **SMTP** → apunta el **Login** (tu email de Brevo) → botón
   **Generate a new SMTP key** → nómbrala `isthistrue` → copia la clave (solo se muestra una vez).
7. En el VPS: `sudo nano /opt/isthistrue/.env` →
   `EMAIL_HOST_USER=tu-login-de-brevo` y `EMAIL_HOST_PASSWORD=la-smtp-key` → guarda →
   **Regla de Oro** (recrear contenedores; el ensure_superuser ya es automático desde el pase 3.4).
8. **Prueba final**: registra una cuenta nueva en escierto.xyztserver.com con un email tuyo real
   → debe llegarte el email de verificación CON DISEÑO (botón negro) → púlsalo → te llega el de
   bienvenida. Si llega a spam la primera vez, márcalo "no es spam" (la reputación se asienta en días).

## 2. PAYPAL.ME — reactivar tu cuenta de hace 20 años
**Metáfora**: tu cuenta PayPal es una tienda que lleva 20 años cerrada: el local es tuyo, pero
antes de vender hay que quitar el polvo (datos al día) y poner un cartel con la dirección corta
(el enlace paypal.me).

**Paso a paso:**
1. Entra en **paypal.com** → Iniciar sesión con `david@xyztserver.com`. Si no recuerdas la
   contraseña: "¿Has olvidado la contraseña?" → recuperación por email. Si la cuenta pide
   verificación extra por antigüedad (SMS a un móvil viejo), usa la opción de confirmar por
   email + datos de la tarjeta/banco.
2. Una vez dentro, **quita el polvo**: ajustes (rueda dentada) → comprueba que tu nombre legal,
   dirección actual y teléfono estén al día; en "Pagos" vincula/confirma una cuenta bancaria o
   tarjeta VIGENTE (las de hace 20 años estarán caducadas). Sin banco vigente puedes RECIBIR,
   pero no retirar el dinero.
3. Crea el cartel: ve a **paypal.me** → "Crea tu enlace PayPal.Me" → elige el nombre
   (sugerencias: `paypal.me/escierto` o `paypal.me/isthistrue` si están libres; si no, tu nombre).
   Foto opcional. ⚠ El enlace muestra el NOMBRE de tu cuenta al donante — como titular persona
   física aparecerá "David Souto Apariz": es normal y coherente con tu aviso legal.
4. Pega el enlace en la web: entra como `d` → `/panel/settings/` → campo `paypal_url` →
   `https://paypal.me/loquesea` → Guardar. La página /donaciones/ activa el botón sola.
5. **Prueba**: abre /donaciones/ en incógnito → botón "Donar por PayPal" → te lleva a tu página.
   Cuando llegue la primera donación real: `/panel/donaciones/` → regístrala → el depósito del
   mes crece al instante y el banner lo refleja.

## 3. BACKUPS — restic + rclone a tu Google Drive (lo que necesito DE TI)
**Metáfora**: restic es un notario que cada noche a las 00:00 fotografía tu proyecto y guarda la
foto CIFRADA en tu trastero de Google (5 TiB). Cada foto parece completa (puedes restaurar
cualquier día entero) pero solo ocupa lo que cambió. Los lunes, además, el notario revisa el
trastero entero por si alguna caja se ha mojado (comprobación de integridad). Guardamos 7 fotos
diarias + 3 semanales — tus "3 copias totales".

**Lo único que necesito de ti** (nadie más puede hacerlo): autorizar a rclone con TU Google.
En el VPS, con Claude Código o conmigo delante:
```
sudo apt install -y restic rclone
sudo rclone config
```
Asistente: `n` (nuevo) → nombre: `gdrive` → tipo: `drive` → client_id/secret: Enter (vacíos)
→ scope: `1` → Enter al resto → te dará un ENLACE: ábrelo en tu navegador, entra con tu cuenta
de Google, acepta, y pega el código de vuelta → `y` para confirmar. Comprueba: `sudo rclone lsd gdrive:`
Luego, el candado del notario (elige una contraseña e IMPRÍMELA o guárdala en Bitwarden — FUERA
del servidor; sin ella los backups son irrecuperables):
```
sudo restic -r rclone:gdrive:isthistrue-backups init
sudo crontab -e
```
Añade esta línea (diaria a las 00:00, tu horario; el propio script hace lo del lunes):
```
0 0 * * * RESTIC_PASSWORD='TU_PASSWORD' /opt/isthistrue/ops/backup/backup.sh >> /var/log/isthistrue-backup.log 2>&1
```
Y la prueba del algodón, AHORA y el día 1 de cada mes:
```
sudo RESTIC_PASSWORD='TU_PASSWORD' restic -r rclone:gdrive:isthistrue-backups restore latest --target /tmp/tr && ls /tmp/tr && sudo rm -rf /tmp/tr
```

## 4. FAIL2BAN — qué es y qué hay que hacer (respuesta: casi nada)
**Metáfora**: fail2ban es el **portero de discoteca de tu VPS**. Se pasa la noche leyendo el
libro de entradas (los logs) y cuando ve a alguien aporrear la puerta con llaves falsas
(5 contraseñas SSH fallidas en 10 minutos), lo veta: su IP queda bloqueada un rato en el
cortafuegos. Sin él, los robots de internet prueban miles de contraseñas contra tu SSH cada
día (esto pasa de verdad, a todos los servidores, siempre).

**Qué hay que configurar**: nada esencial — ya está instalado y activo con la cárcel de SSH
por defecto. Comprobaciones y ajuste fino opcional:
```
sudo systemctl status fail2ban          # debe decir "active (running)"
sudo fail2ban-client status sshd        # cuántos vetados ahora y en total
```
Ajuste opcional recomendado (vetos más largos a reincidentes), archivo nuevo:
```
sudo nano /etc/fail2ban/jail.local
```
```
[sshd]
enabled = true
port = 22222
maxretry = 5
bantime = 1h
[recidive]
enabled = true
bantime = 1w
findtime = 1d
maxretry = 3
```
(⚠ `port = 22222` porque tu SSH va por ese puerto — si no se lo dices, vigila la puerta equivocada.)
```
sudo systemctl restart fail2ban
```
Mi recomendación: déjalo activo para siempre. No molesta, no consume, y es la diferencia entre
un log lleno de intentos y un log lleno de intentos VETADOS.
