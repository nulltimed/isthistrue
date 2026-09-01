# Informe — Parche 5.0-A: la mudanza a esestocierto.com

**Fecha:** 2026-09-01 · **Desarrollo y operación:** Claude Code (Fable 5)
**Commit:** `e5a9c38` · **CI:** verde (348 tests) · **Producción:** desplegado y verificado en vivo

---

## 1. La casa nueva, completa

| Pieza | Estado |
|---|---|
| `esestocierto.com` + `www` + `wiki` | **HTTPS con certificado válido**, CSS y portada verdes, **logo en español** |
| Renovación de certificados | Automática (certbot vía snap; simulacro de renovación pasado) |
| Dominios históricos | **301 permanente** — isthistrue/escierto → `esestocierto.com`; wikitrue → `wiki.esestocierto.com`. Ningún enlace viejo muere |
| El timbre de AssemblyAI | Re-apuntado a la casa nueva y verificado (403 sin secreto) |
| Identidad interna | `ALLOWED_HOSTS`/CSRF, parents de Twitch, atribución de la API — todo migrado |
| Brevo | Remitente `mail.esestocierto.com` verificado por David; **email de prueba ENTREGADO** en su buzón (confirmado en el log del correo del host — sin tocar el Postfix personal) |

## 2. La guía DNS que siguió David (para el registro)

Tres registros A al VPS (`@`, `www`, `wiki`) + los registros de verificación que Brevo dicta
(CNAME de firma + TXT SPF), pegados tal cual en IONOS. Todo propagó a la primera.

## 3. Hitos del día que no eran de este parche pero lo enmarcaron

- **El timbre completó su primer vuelo real solo**: el vigía nocturno relanzó el post 5 con el
  depósito de septiembre, AssemblyAI llamó a `/aai-hook/`, la reanudación creó las 336
  intervenciones y el post llegó a **DONE** — cadena entera sin humanos ni workers esperando.
- David dio por buena la calidad de transcripción/diarización del post 5 para el estándar de
  la web: el listón acordado.

## 4. Pendientes de la serie 5.x

- **5.0-B**: URLs `/post/nombre-legible/2` con 301 desde las numéricas (sin decisiones pendientes; siguiente).
- **5.1 (wiki-red)**: esperando las tres decisiones de David — quién crea los temas, si el
  estreno del dominio abre las fichas a Google (`wiki_index_people`), e idioma por defecto.
- Menores: ¿el email de prueba llegó a bandeja o a spam? (decide si añadimos DMARC). Aviso
  ajeno al proyecto: el certificado de `autocryptcom.xyztserver.com` (otro proyecto de David)
  está fallando su renovación.
