# install.md — Guía completa de instalación, despliegue, funcionamiento y pruebas
## isthistrue. / escierto. — desde CERO absoluto
> Dos partes: **A) Windows 11 (EliteBook, desarrollo)** y **B) VPS Ubuntu 24.04 (producción)**.
> Cada paso lleva sus comandos exactos. Si algo falla, apunta el número de paso y el mensaje literal, y repórtalo todo de una vez al terminar.
> Convención: los comandos empiezan por `$` (no escribas el `$`). Los que empiezan por `PS>` van en PowerShell de Windows.

---

# PARTE 0 — GitHub y el portero (hazlo ANTES de tocar el VPS)

> Aún no se ha hecho ningún push: este es el momento. Con el repo creado, el VPS se instala con `git clone` y cada actualización es `git pull`. Y el CI (el portero) se estrena solo.
> Esta parte puede ejecutarla Claude Código directamente (lee CLAUDE.md en la raíz del proyecto); David solo crea la cuenta GitHub `nulltimed` y el repo vacío `isthistrue` si no existen, y añade la llave SSH.

1. Sigue la mini-guía de Git ya entregada: cuenta GitHub `nulltimed` → repo nuevo **isthistrue** (Public, SIN marcar "Add README" ni licencia) → llave SSH → en la carpeta del proyecto descomprimido:
```
$ cd ~/isthistrue     # o donde hayas descomprimido el ZIP
$ cat .gitignore | grep .env      # DEBE aparecer .env; si no, PARA y avisa
$ git init && git add . && git status    # si ves .env en verde, PARA y avisa
$ git commit -m "Hito 2A revisado + Hito 2B"
$ git branch -M main
$ git remote add origin git@github.com:nulltimed/isthistrue.git
$ git push -u origin main
```
2. Abre github.com/nulltimed/isthistrue → pestaña **Actions**: verás el CI corriendo (círculo amarillo). En 3-5 min: ✅ verde (adelante) o ❌ rojo (mándame el enlace del fallo y no sigas).

---

# PARTE A — (ELIMINADA)
> Decisión de David: no se desplegará NUNCA nada en el EliteBook. Todo ocurre en el VPS:
> el espejo (Parte C) es el único entorno de pruebas. La gestión de Git y el despliegue
> los ejecuta Claude Código (app de Windows) siguiendo CLAUDE.md, con supervisión de David.

---

# PARTE B — VPS IONOS Ubuntu 24.04 (producción)

> **Regla de oro**: en el host ya corren Nginx, PostgreSQL, Postfix+Dovecot, Grafana y Prometheus. **No se toca ninguno.** Nuestro stack vive en Docker, solo en `127.0.0.1:8090`, y el Nginx del host hace de portero.

## B1. Conectar y preparar

Desde tu EliteBook (terminal Ubuntu/WSL), con tu usuario administrador de siempre:
```
$ ssh TU_ADMIN@IP_DEL_VPS
```

## B2. Instalar Docker Engine (si no está ya)

```
$ docker --version || curl -fsSL https://get.docker.com | sudo sh
$ sudo systemctl enable --now docker
$ docker compose version
```

## B3. Crear el usuario de servicio `i` (sin contraseña, sin shell, sin SSH)

```
$ sudo useradd -r -m -d /opt/isthistrue-home -s /usr/sbin/nologin i
$ sudo usermod -aG docker i
$ id i
```
Debe mostrar el grupo `docker`. Este usuario NO puede iniciar sesión: solo ejecuta el stack. **Tu SSH de administrador se conserva intacto** (puerta principal sí; backdoors, cero).

## B4. Subir el proyecto

Opción recomendada (desde el repo, cuando exista):
```
$ sudo mkdir -p /opt/isthistrue && cd /opt
$ sudo git clone https://github.com/nulltimed/isthistrue.git
```
Opción directa (subir el ZIP desde el EliteBook; ejecuta esto en el EliteBook, no en el VPS):
```
$ scp ~/isthistrue-hito2a.zip TU_ADMIN@IP_DEL_VPS:/tmp/
```
Y de vuelta en el VPS:
```
$ sudo apt install -y unzip && sudo unzip /tmp/isthistrue-hito2a.zip -d /opt/ && sudo rm /tmp/isthistrue-hito2a.zip
```
Permisos:
```
$ sudo chown -R i:i /opt/isthistrue
```

## B5. Configuración de producción (.env)

```
$ cd /opt/isthistrue
$ sudo -u i cp .env.example .env
$ sudo -u i nano .env
$ sudo chmod 600 .env
```
Valores de producción (los que cambian respecto a desarrollo):
- `DEBUG=False`  ← imprescindible
- `SECRET_KEY=` cadena larga aleatoria NUEVA (no la de desarrollo)
- `POSTGRES_PASSWORD=` contraseña fuerte nueva
- `ANTHROPIC_API_KEY=` tu clave real (console.anthropic.com; **fija allí el límite mensual = doble airbag**)
- `MOCK_AGENTS=false`
- `TURNSTILE_SITE_KEY=` y `TURNSTILE_SECRET_KEY=` (Cloudflare)
- `EMAIL_HOST_USER=` y `EMAIL_HOST_PASSWORD=` (Brevo SMTP)

## B6. Arrancar el stack (siempre como `i`)

```
$ cd /opt/isthistrue
$ sudo -u i docker compose up --build -d
$ sudo -u i docker compose ps
$ sudo -u i docker compose exec db psql -U isthistrue -c "CREATE EXTENSION IF NOT EXISTS vector;"
$ sudo -u i docker compose exec web python manage.py makemigrations accounts analysis wiki forum panel
$ sudo -u i docker compose exec web python manage.py migrate
$ sudo -u i docker compose exec web python manage.py seed_settings
$ sudo -u i docker compose exec web python manage.py createsuperuser
$ sudo -u i docker compose exec web python manage.py collectstatic --noinput
```
Comprobación local (el stack NO es visible desde fuera todavía, y así debe ser):
```
$ curl -I http://127.0.0.1:8090
```
Debe responder `HTTP/1.1 200` (o 301/302).

## B7. DNS en IONOS

En el panel de IONOS del dominio `xyztserver.com`, crea **3 registros A** apuntando a la IP del VPS:
- `isthistrue` · `escierto` · `wikitrue`

Espera a que propaguen (minutos a horas). Comprueba desde el EliteBook:
```
$ ping -c1 isthistrue.xyztserver.com
```

## B8. Nginx del host (el portero) + HTTPS

```
$ sudo cp /opt/isthistrue/nginx/isthistrue-host.conf /etc/nginx/sites-available/isthistrue.conf
$ sudo ln -s /etc/nginx/sites-available/isthistrue.conf /etc/nginx/sites-enabled/
$ sudo nginx -t
$ sudo systemctl reload nginx
```
`nginx -t` DEBE decir "syntax is ok / test is successful". Si no, NO recargues: revisa el mensaje (lo más común: conflicto de `server_name` con otro sitio tuyo).

Certificados (certbot ya instalado si lo usas para tus otros dominios; si no: `sudo apt install -y certbot python3-certbot-nginx`):
```
$ sudo certbot --nginx -d isthistrue.xyztserver.com -d escierto.xyztserver.com -d wikitrue.xyztserver.com
```

Página de pánico estática:
```
$ sudo mkdir -p /var/www/isthistrue-panic
$ echo '<!doctype html><meta charset="utf-8"><body style="font-family:Courier,monospace;font-weight:bold;display:grid;place-items:center;height:100vh"><div>Servicio pausado por el administrador.<br>Trabajando en ello...</div>' | sudo tee /var/www/isthistrue-panic/panic.html
```
(La versión con la tipografía quemada del logo llega con el frontend definitivo.)

Prueba final: abre `https://escierto.xyztserver.com` desde el móvil (fuera de tu wifi, para probar de verdad desde Internet).

## B9. Cortafuegos y fail2ban

⚠ **Antes de activar ufw, permite el SSH o te quedas fuera del servidor:**
```
$ sudo ufw allow OpenSSH
$ sudo ufw allow 80/tcp
$ sudo ufw allow 443/tcp
$ sudo ufw enable
$ sudo ufw status
$ sudo apt install -y fail2ban && sudo systemctl enable --now fail2ban
```
(Si tu mail personal necesita otros puertos —25/465/587/993— y ya los usabas, añádelos ANTES de `enable`.)

## B10. Backups (restic → VIM3 + Google Drive; ruta RENOMBRADA)

En el **VIM3** (por SSH/VPN Mullvad), crea la carpeta nueva:
```
$ mkdir -p /mnt/server/backups/isthistrue
```
En el **VPS**:
```
$ sudo apt install -y restic rclone
$ sudo mkdir -p /root/.config
```
Alias SSH del VIM3 para restic (edita IP/usuario reales de tu VPN):
```
$ sudo nano /root/.ssh/config
```
```
Host vim3
    HostName IP_VPN_DEL_VIM3
    User TU_USUARIO_VIM3
    IdentityFile /root/.ssh/id_ed25519
```
Genera clave e instálala en el VIM3:
```
$ sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
$ sudo cat /root/.ssh/id_ed25519.pub   # copia esta línea a ~/.ssh/authorized_keys del VIM3
```
Inicializa el repositorio cifrado (la contraseña que elijas es **RESTIC_PASSWORD: guárdala FUERA del servidor; sin ella los backups son irrecuperables**):
```
$ sudo restic -r sftp:vim3:/mnt/server/backups/isthistrue init
```
Configura rclone para Google Drive (asistente interactivo; nombre del remoto: `gdrive`):
```
$ sudo rclone config
```
Cron (diarias 5:00; el propio script hace la retención y el espejo a GDrive):
```
$ sudo crontab -e
```
```
0 5 * * * RESTIC_PASSWORD='TU_PASSWORD_RESTIC' /opt/isthistrue/ops/backup/backup.sh >> /var/log/isthistrue-backup.log 2>&1
```
**Test de restauración** (hazlo AHORA una vez, y luego el día 1 de cada mes — "una copia no probada es una esperanza"):
```
$ sudo RESTIC_PASSWORD='TU_PASSWORD_RESTIC' restic -r sftp:vim3:/mnt/server/backups/isthistrue snapshots
$ sudo RESTIC_PASSWORD='TU_PASSWORD_RESTIC' restic -r sftp:vim3:/mnt/server/backups/isthistrue restore latest --target /tmp/test-restore && ls /tmp/test-restore && sudo rm -rf /tmp/test-restore
```
Tercera línea: los snapshots de IONOS ya contratados siguen activos por su cuenta.

## B11. Operación diaria en producción

```
$ cd /opt/isthistrue
$ sudo -u i docker compose ps                      # estado
$ sudo -u i docker compose logs -f --tail=100 web  # logs web
$ sudo -u i docker compose logs -f --tail=100 worker
$ sudo -u i docker compose restart web             # reinicio suave
$ sudo -u i docker compose down && sudo -u i docker compose up -d   # reinicio total
```
**Actualizar a una versión nueva** (cuando recibas un ZIP/commit nuevo):
```
$ cd /opt/isthistrue
$ sudo -u i docker compose down
$ sudo cp -r /opt/isthistrue /opt/isthistrue.bak-$(date +%F)   # .bak por si acaso
# (sustituir el código: git pull, o descomprimir el ZIP nuevo ENCIMA conservando el .env)
$ sudo chown -R i:i /opt/isthistrue
$ sudo -u i docker compose up --build -d
$ sudo -u i docker compose exec web python manage.py migrate
$ sudo -u i docker compose exec web python manage.py collectstatic --noinput
```

## B12. Diagnóstico rápido de problemas

| Síntoma | Comprobación | Remedio habitual |
|---|---|---|
| La web no carga desde fuera | `curl -I http://127.0.0.1:8090` en el VPS | Si responde: problema de Nginx/DNS/certbot (B7-B8). Si no: `docker compose ps` y logs de web |
| 502 Bad Gateway | `sudo -u i docker compose ps` | El contenedor web está caído: mira sus logs y rearranca |
| Análisis se quedan en "Nuevo" | logs del worker | Presupuesto agotado (normal: espera al día siguiente) o worker caído |
| Emails no llegan | `.env` de Brevo + logs web | Credenciales SMTP o DKIM/DMARC sin propagar en IONOS |
| `permission denied` con docker | `id i` | Falta el grupo docker: B3, y reinicia sesión |
| Migración falla con "vector" | — | `CREATE EXTENSION vector` (B6, primera orden) |


---

# PARTE C — EL ESPEJO DE PRUEBAS (staging en el VPS) — camino oficial

> Metáfora: el ensayo general antes del estreno. Nada llega a producción sin pasar por aquí.
> El espejo va APAGADO por defecto y SIEMPRE en modo simulado (jamás gasta depósito).

## C1. Preparar (una sola vez)

```
$ sudo cp -r /opt/isthistrue /opt/isthistrue-staging
$ sudo chown -R i:i /opt/isthistrue-staging
$ cd /opt/isthistrue-staging && sudo -u i nano .env
```
En el `.env` del espejo cambia: `STAGING_MODE=true` (el compose ya lo fuerza igualmente, doble seguro).

DNS: crea el **cuarto registro A** en IONOS: nombre `staging` (a secas) → IP del VPS → resultado stagings.xyztserver.com. Nginx y HTTPS:
```
$ sudo nginx -t && sudo systemctl reload nginx     # el bloque staging ya está en isthistrue-host.conf
$ sudo certbot --nginx -d stagings.xyztserver.com
```
(Capa 2 opcional de contraseña: descomenta las dos líneas `auth_basic` del bloque staging y `sudo htpasswd -c /etc/nginx/.htpasswd-staging d`.)

## C2. Encender el espejo (cada vez que haya versión que ensayar)

```
$ cd /opt/isthistrue-staging
$ sudo -u i docker compose -f docker-compose.staging.yml -p staging up --build -d
$ sudo -u i docker compose -f docker-compose.staging.yml -p staging exec db psql -U isthistrue -c "CREATE EXTENSION IF NOT EXISTS vector;"
$ sudo -u i docker compose -f docker-compose.staging.yml -p staging exec web python manage.py makemigrations accounts analysis wiki forum panel
$ sudo -u i docker compose -f docker-compose.staging.yml -p staging exec web python manage.py migrate
$ sudo -u i docker compose -f docker-compose.staging.yml -p staging exec web python manage.py seed_settings
$ sudo -u i docker compose -f docker-compose.staging.yml -p staging exec web python manage.py seed_forum
$ sudo -u i docker compose -f docker-compose.staging.yml -p staging exec web python manage.py createsuperuser
```
Entra en https://stagings.xyztserver.com con el superusuario (los invitados se gestionan en Panel → Espejo, por email). Pasa el checklist completo del `docs/04-checklist-verificacion.md` contra el espejo.

## C3. Apagar el espejo (libera los ~2-3 GB de RAM)

```
$ cd /opt/isthistrue-staging
$ sudo -u i docker compose -f docker-compose.staging.yml -p staging down
```

## C4. El ritual completo de cada versión nueva

1. `git push` → espera el ✅ verde del CI en GitHub (2-3 min). Rojo = no sigas: mándame el enlace del fallo.
2. Actualiza el código del espejo (`git pull` en /opt/isthistrue-staging) → C2 → checklist.
3. Si el checklist pasa: C3 (apaga el espejo) y despliega a producción (B11, "Actualizar a una versión nueva").

## C5. El robot de tests, a mano cuando quieras

```
$ sudo -u i docker compose exec web python manage.py test tests --settings=tests.settings_test
```
En un minuto: OK o qué circuito vital se rompió (candados de presupuesto, votaciones, códigos, relegación, edad mínima).


---

# PARTE D — Pasos nuevos del Hito 2B (dentro del despliegue del VPS)

## D1. Token de Hugging Face (para la diarización — separar hablantes)

Metáfora: el carnet de la biblioteca de modelos de IA. Gratis, pero sin él no te prestan el modelo.
1. Entra en **huggingface.co** → Sign Up (email + contraseña; confirma el email).
2. Visita estas DOS páginas (logueado) y pulsa el botón de aceptar condiciones en cada una — **si te saltas esto, el token no funcionará** (es el fallo más común):
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. Tu avatar (arriba a la derecha) → **Settings** → **Access Tokens** → **New token** → nombre `isthistrue`, tipo **Read** → Create → copia el texto que empieza por `hf_`.
4. En el VPS: `sudo -u i nano /opt/isthistrue/.env` → pega en `HF_TOKEN=hf_...` → guarda → reinicia el worker:
```
$ cd /opt/isthistrue && sudo -u i docker compose restart worker
```
Sin token, todo funciona igual pero sin separar hablantes (puedes añadirlo cuando quieras).

## D2. Verificar Tesseract (OCR de rótulos) — ya viene en la imagen

```
$ sudo -u i docker compose exec worker tesseract --version
```
Debe responder con la versión. Si dice "not found": reconstruye la imagen (`sudo -u i docker compose up --build -d`), porque el Dockerfile nuevo lo instala.

## D3. Comprobar la API por lotes

Con `USE_BATCH_API=true` (por defecto) y tu clave de Anthropic puesta, el primer análisis validado aparecerá en los logs del worker como `batch_submitted` y pasará a "Analizado" en minutos. Si algo del lote falla, el sistema cae solo a llamadas directas: no tienes que hacer nada.

## D4. Checklist adicional del 2B (tras el checklist general)

23. **Hablantes**: en un post analizado (mock), la transcripción muestra etiquetas SPEAKER_1/SPEAKER_2 y el bloque "¿Quién habla?" con un candidato `[SIMULADO]`.
24. **Voto de nombre**: como "d", vota al candidato → con el peso de moderador (5 puntos) debe confirmarse al primer voto (✔).
25. **Tarjeta compartible**: abre /wiki/claim/<slug>/tarjeta.png → debe verse el PNG con la franja del color del semáforo.
26. **Seguir claim**: pulsa "Seguir este claim"; fuerza una re-verificación cambiando el mock y comprueba el aviso en la campana (o déjalo anotado para probar con API real).
27. **Amistad**: desde dos cuentas, solicitud → aceptar; comprueba que desactivar "Permitir solicitudes" en ajustes bloquea nuevas; prueba "Bloquear".
28. **Markdown**: escribe **negrita** y [enlace](https://example.org) en un comentario del foro → debe renderizarse; escribe <script>alert(1)</script> → debe verse como texto plano (escapado).
29. **Legales**: el aviso legal muestra "David Souto Apariz" y contact@xyztserver.com, y NO contiene tu domicilio real. El campo del apartado de correos queda [pendiente] hasta que lo contrates.
