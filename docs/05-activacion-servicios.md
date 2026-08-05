# GUÍA MAESTRA — Activar y desplegar TODOS los servicios (paso a paso, desde cero)
> Cada sección es independiente: hazlas en este orden cuando quieras. Tras CUALQUIER
> cambio en el `.env`, aplica SIEMPRE la Regla de Oro del paso 0.

## 0. REGLA DE ORO del .env (la causa de tu problema de login)
El `.env` solo se lee al CREAR los contenedores. Tras editarlo:
```
cd /opt/isthistrue
sudo -u i docker compose up -d --force-recreate web worker beat
sudo -u i docker compose exec web python manage.py ensure_superuser
```
(`restart` NO recarga el .env; `ensure_superuser` vuelca ADMIN_EMAIL/ADMIN_PASSWORD a la base de datos.)
Entras con `d` o con tu ADMIN_EMAIL, y la ADMIN_PASSWORD del .env.

## 1. Presupuesto nuevo (decidido: 100 €/mes, 3 €/día)
1. `sudo nano /opt/isthistrue/.env` → `DAILY_BUDGET_EUR=3.00` y `MONTHLY_CAP_EUR=100` → Regla de Oro.
2. Entra como d → `/panel/settings/` → `budget_base_eur` = **100** (el techo vivo = 100 + donaciones, tope duro 200).

## 2. Anthropic (los agentes de verdad — hasta ahora todo es [SIMULADO])
1. Ve a **console.anthropic.com** → Sign up (cuenta NUEVA de API, separada de tu Claude Pro).
2. Menú **Billing** → añade tarjeta → carga inicial **50 €** (suficiente para arrancar; recargarás cuando toque).
3. Menú **Limits** (o Settings→Limits) → **límite mensual de gasto: 200 €** ← el techo duro del código es 200; este es el segundo airbag: DEBEN coincidir.
4. Menú **API Keys** → Create key → nómbrala `isthistrue-prod` → copia el `sk-ant-...` (solo se muestra una vez).
5. `.env`: `ANTHROPIC_API_KEY=sk-ant-...` y `MOCK_AGENTS=false` → Regla de Oro.
6. Prueba: analiza un vídeo corto real → la transcripción ya no dirá [SIMULADO]. ⚠ Desde este momento cada análisis cuesta dinero de verdad (fase barata ~0,05 €).

## 3. Brevo (emails: verificación de cuentas, notificaciones, alertas admin)
1. **brevo.com** → Sign up gratis (300 emails/día) → confirma tu email.
2. Menú **Senders, Domains & Dedicated IPs** → **Domains** → Add domain: `xyztserver.com`.
3. Brevo te dará **2-3 registros DNS** (tipo TXT: uno `mail._domainkey...` para DKIM, otro de verificación, y sugerencia DMARC). En el panel DNS de **IONOS** de xyztserver.com: **añade** esos TXT exactamente como te los da (⚠ AÑADIR, no tocar NADA existente — tu correo personal vive ahí).
4. Espera 10-60 min → botón "Verify" en Brevo hasta que salga verde.
5. Menú **SMTP & API** → pestaña **SMTP** → copia el **Login** (tu email de Brevo) y crea una **SMTP key** (contraseña).
6. `.env`: `EMAIL_HOST_USER=<login>` y `EMAIL_HOST_PASSWORD=<smtp-key>` → Regla de Oro.
7. Prueba: registra una cuenta nueva en escierto.xyztserver.com → debe llegarte el email de verificación de verdad.

## 4. Cloudflare Turnstile (anti-bots del registro)
1. **dash.cloudflare.com** → Sign up → en el menú lateral: **Turnstile** → Add site.
2. Nombre `isthistrue` · dominios: `isthistrue.xyztserver.com`, `escierto.xyztserver.com` · modo **Managed** → Create.
3. Copia **Site Key** y **Secret Key** → `.env`: `TURNSTILE_SITE_KEY=` y `TURNSTILE_SECRET_KEY=` → Regla de Oro.
4. Prueba: el formulario de registro muestra el widget de verificación.
(El DNS NO se toca: sigue en IONOS. Solo usamos el producto Turnstile.)

## 5. Hugging Face (diarización de hablantes)
1. **huggingface.co** → Sign up → confirma email.
2. LOGUEADO, visita y acepta condiciones en AMBAS páginas (si te lo saltas, el token no sirve):
   huggingface.co/pyannote/speaker-diarization-3.1 y huggingface.co/pyannote/segmentation-3.0
3. Avatar → Settings → Access Tokens → New token → tipo **Read** → nombre `isthistrue` → copia el `hf_...`.
4. `.env`: `HF_TOKEN=hf_...` → Regla de Oro. Prueba: nuevo análisis → etiquetas SPEAKER_1/2 reales.

## 6. CI de GitHub (token workflow YA arreglado por David)
Dile a Claude Código: "sube el ci.yml pendiente" (él sabe: `git add -f .github/workflows/ci.yml`,
quitar la exclusión, commit, push). Comprueba: github.com/nulltimed/isthistrue → **Actions** → ✅ verde.
Desde entonces, el portero vigila cada push de verdad.

## 7. Panel: ajustes vivos (como d, en /panel/settings/ y /panel/donaciones/)
- `budget_base_eur=100` · `donation_goal_eur` (sugerido 100) · `paypal_url` (cuando exista, paso 8).
- Umbrales por defecto ya sembrados: 70/5min, 5/10/3días, arranque 50, Opus 40%/50.

## 8. PayPal.me (donaciones) — [PARA DESPUÉS, recordatorio activo]
1. paypal.com → cuenta personal → verifica banco/tarjeta.
2. paypal.me → crea tu enlace (p. ej. paypal.me/tunombre).
3. Pégalo en `/panel/settings/` → `paypal_url`. La página /donaciones/ activa el botón sola.

## 9. Permisos del foro machina — [PARA DESPUÉS, recordatorio activo]
Como d → `/admin/` → sección **Forum permissions** → concede a usuarios autenticados leer/responder
en Principal y Off-Topic (roce conocido del checklist: sin esto, no se puede comentar).

## 10. Backups (restic → Google Drive) — [PARA DESPUÉS, recordatorio activo]
Sigue install.md B10 (rclone config interactivo con tu Google, restic init, cron 5:00,
RESTIC_PASSWORD guardada FUERA del servidor, test de restauración). Requiere tu sesión de Google: hazlo conmigo o con Claude Código delante.

## 11. fail2ban — [PARA DESPUÉS, recordatorio activo]
Está reinstalado y activo. Confirma que lo quieres (recomendado: sí) o pide dejarlo como estaba.

## 12. Apartado de correos — [PARA DESPUÉS, recordatorio activo]
Contratar en Correos (~60-80 €/año) y sustituir "[APARTADO DE CORREOS — pendiente]" del aviso legal.
