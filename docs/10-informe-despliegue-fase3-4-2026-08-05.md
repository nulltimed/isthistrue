# Informe de despliegue — Fase 3.4 (2026-08-05)

> Operador: Claude Código. Paquete MÍNIMO aplicado según README-OPERADOR-FASE3-4.md.
> Ritual canónico completo. Run verde: https://github.com/nulltimed/isthistrue/actions/runs/31033446790

## ⚠️ ACCIÓN URGENTE DAVID — DNS de isthistrue.xyztserver.com roto (ajeno al despliegue)

Durante la verificación final descubrí que **isthistrue.xyztserver.com ya no apunta al VPS**:
```
isthistrue.xyztserver.com → CNAME isthistrue-xyztserver-com.brand.brevosend.com → 94.143.16.132 (Brevo)
```
Resultado: ese dominio da timeout desde Internet (la petición va a un servidor de Brevo). escierto y wikitrue siguen perfectos, y la app responde bien para los tres hosts en loopback: **no es un problema del código ni del stack, es el registro DNS**.
Diagnóstico probable: al preparar Brevo en IONOS se creó el registro de "branding" de Brevo SOBRE el dominio principal. **Arreglo en el panel IONOS**: restaurar el registro **A `isthistrue` → 217.154.23.57** y poner el CNAME de Brevo en el subdominio que Brevo pida (suelen ser subdominios propios de envío/DKIM, nunca el dominio del sitio web). Ojo: mientras esté así, la renovación del certificado de ese dominio también fallará.

## Resultado en una línea

**Fase 3.4 EN PRODUCCIÓN**: CSRF de navegador arreglado (EL objetivo del pase), superusuario auto-sincronizado en cada arranque, cabecera nueva con logo grande centrado, emails HTML de verificación+bienvenida, moderación reproducible en espejo, y limpieza de los flecos §9/§10. Tests en verde, checklist 49-54 completo (49 verificado también en producción).

## El bug CSRF (parche §1) — por qué mis tests anteriores no lo veían

HTTPS termina en el Nginx del host y Django recibía HTTP interno. Un navegador real envía cabecera `Origin: https://…` en los POST; Django, creyéndose en http, la rechazaba → **403 en todos los formularios desde navegador**. Mis curls de checklists anteriores no enviaban `Origin`, así que pasaban — falsa confianza, lección aprendida: **todas las verificaciones de login/formularios llevan ahora `Origin` como un navegador**. Arreglo: `CSRF_TRUSTED_ORIGINS` (derivado de ALLOWED_HOSTS) + `SECURE_PROXY_SSL_HEADER`.

## Qué se aplicó (guía §1-§6)

1. §1 Parche CSRF en settings (producción y espejo comparten settings: un solo cambio).
2. §2 `ensure_superuser` en el `command` del web en ambos composes → se ejecuta en cada arranque (visto en logs de espejo y producción). Adiós a la incidencia ".env editado sin comando".
3. §3 Archivos del paquete: cabecera nueva (logo grande centrado + ES|EN + nav), logos SVG grandes, `verification.py` con emails multipart, plantillas `emails/verify.html`+`welcome.html`, `backup.sh` con tu calendario (00:00 diaria, 7d+3s, lunes `restic check`), `docs/07-guias-david.md`.
4. §4 Email de bienvenida al verificar (parche en `verify_email`).
5. §5 Mock de moderación sensible al contenido (la palabra "insulto" dispara el flag).
6. §6 Limpieza: `should_opus_rescan` eliminada (única puerta: `maybe_trigger_opus_rescan` desde `upvote`), README §25 consolidado en la versión DEFINITIVA, avatares confirmados en **Haiku**.

## Arreglos del operador sobre el paquete (commit 954824e)

1. **El test `OpusRescan` usaba la función que la guía mandaba borrar** — borrarla a secas habría puesto el CI en rojo. Reescribí el test contra `maybe_trigger_opus_rescan` (mockeando `.delay`) conservando la cobertura del umbral positivo, el negativo y el "una sola vez".
2. `verification.py` traía una función muerta `_brand()` con un `or True` que la hacía devolver siempre lo mismo; nada la usaba: eliminada.
3. `seed_settings` aún sembraba `opus_rescan_min_votes`, clave huérfana tras borrar `should_opus_rescan`: retirada.

## Checklist §7 del pase

- **49.** ✔ Login POST por HTTPS **con Origin** como navegador real: `d` → 302 y `david@xyztserver.com` → 302, en espejo y en producción (escierto).
- **50.** ✔ Logo grande centrado arriba, ES|EN y nav centrada (verificado en escierto y wikitrue; isthistrue pendiente del DNS de arriba — en loopback sirve idéntico).
- **51.** ✔ Email de verificación multipart texto+HTML y bienvenida tras verificar (consola del espejo: `multipart/alternative` con `text/plain`+`text/html` en ambos).
- **52.** ✔ Comentario con "insulto" → `approved=False` + expediente `NOVICE_DECIDED/BLOCK`; comentario limpio → publicado. Reproducible por UI sin parches.
- **53.** ✔ `Superusuario 'd' actualizado desde .env.` en los logs de arranque del web (espejo y producción).
- **54.** ✔ `backup.sh` nuevo en su sitio (ejecutable). Cron NO activado (te espera con la guía docs/07-guias-david.md y tu rclone).

## Estado final

- **Producción**: commit `954824e` + docs, 6 contenedores Up, logs limpios. escierto/wikitrue perfectos por HTTPS; isthistrue bloqueado SOLO por su DNS (ver arriba).
- **Espejo**: mismo commit, APAGADO.
- **GitHub**: main = VPS = espejo; [CI verde](https://github.com/nulltimed/isthistrue/actions/runs/31033446790).
- **PENDIENTE DAVID**: 1) el DNS de isthistrue (urgente, arriba); 2) el resto sigue en pausa como pediste (Brevo/PayPal/backups/fail2ban — guías nuevas en docs/07-guias-david.md cuando toque).
