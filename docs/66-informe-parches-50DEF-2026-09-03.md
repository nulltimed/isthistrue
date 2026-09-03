# Informe de los parches 5.0-D, 5.0-E y 5.0-F (2026-09-03)

**Commits:** `bd237c8` (D) · `c4826c6` (E) · `6e3f10f` (F) · `0028760` (arreglos del CI).

## 5.0-D — la URL del post pierde el número
`/post/nombre-del-video-legible/` como canónica (corrección de David sobre el 5.0-C).
Slug ÚNICO: el duplicado recibe `-2`, `-3`…; un título solo-números se protege con
`-video`. La numérica y la forma slug/pk hacen 301 conservando la query. Migración 0017
(NULL + dedupe + unique). Además: `www.esestocierto.com` → 301 al dominio sin www
(bloque propio en el nginx del host; el .bak NUNCA se deja en sites-enabled — nginx
carga todos los ficheros del directorio y los server_name duplicados se ignoran en
silencio).

## 5.0-E — la cuenta completa (los seis huecos)
1. **Recuperar contraseña olvidada** (no existía: quien la perdía, perdía la cuenta).
2. **Cambiar contraseña** desde dentro.
3. **Cambiar email**: el enlace viaja al buzón NUEVO; el token firmado lleva el email
   dentro (sin campo pendiente, sin migración).
4. **Exportar mis datos** (RGPD art. 20): JSON con perfil, ajustes, posts, mensajes
   propios, amistades y bloqueos.
5. **Bloqueos con llave**: desbloquear + lista en Amigos + botón en el buzón de MP.
6. **2FA TOTP** opcional: QR en SVG (qrcode ya estaba en requirements), el login pide
   el código ANTES de abrir sesión, baja con código.

El CI cazó tres cosas (todas arregladas en `0028760`): `effective_level` es un MÉTODO
(el export lo serializaba sin llamar), el candado anti-reutilización del TOTP rechaza el
mismo código dos veces (correcto; el test resetea `last_t`), y el candado i18n exigió
las 39 cadenas nuevas en el catálogo EN.

## 5.0-F — legales redactados de verdad + contacto
Fin de los «[PLANTILLA]»: aviso legal, privacidad, cookies y condiciones completos en
ES y EN con el quiz de David (todo por defecto): titular persona física + asociación en
constitución; apartado de correos pendiente (el domicilio real jamás); encargados al
día (IONOS, Brevo, Anthropic, AssemblyAI, Runpod, PayPal, Turnstile); sin analítica →
sin banner de cookies; edad mínima 14. La portabilidad/supresión enlazan los botones
REALES del 5.0-E. Footer: Contacto (webmaster@esestocierto.com) en todas las páginas.

## Correo del dominio (fuera del repo, en el host — orden expresa de David)
- Buzón `webmaster@esestocierto.com` en Dovecot (passwd-file `/etc/dovecot/users`,
  maildir vmail) + alias `postmaster@`, `abuse@` y `david@` → david@xyztserver.com.
- `esestocierto.com` añadido a `virtual_mailbox_domains` de Postfix; mapas con postmap.
- Probado: entrega al buzón nuevo, alias y REGRESIÓN de @xyztserver.com — tres en verde.
- Copias de seguridad de los 4 ficheros tocados en /root/mail-baks-*.
- **PENDIENTE DE DAVID**: registro MX en IONOS (`@ MX 10 mail.xyztserver.com`) para que
  el correo EXTERNO pueda llegar. Cliente de correo: IMAP mail.xyztserver.com:993,
  SMTP :587, usuario el email completo.

## ⏰ Recordatorio de Google — CUMPLIDO
El contador de iteraciones llegó a 5 (B=1, C=2, D=3, E=4, F=5): el aviso de abrir las
fichas a Google (`wiki_index_people` en el panel) se le da a David en el informe de hoy.
