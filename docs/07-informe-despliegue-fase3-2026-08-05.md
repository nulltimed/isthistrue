# Informe de despliegue — Fase 3 (2026-08-05, tarde)

> Operador: Claude Código. ZIP `isthistrue-fase3.zip` aplicado según el protocolo del CLAUDE.md
> (sobre el árbol git, nunca sustitución ciega), ensayado en el espejo y desplegado a producción.

## Resultado en una línea

**La Fase 3 está EN PRODUCCIÓN** en los 3 dominios (HTTPS OK) tras pasar tests (10/10) y checklist del espejo. `stagings.xyztserver.com` ya tiene su certificado. Copia de seguridad previa en `/opt/isthistrue.bak-2026-08-05`.

## Qué trae la Fase 3 (verificado funcionando en el espejo)

- **Portada por secciones**: Recientes / Más votados (7 días) / Reincidentes / Por tema (12 temas + tags) / Off-Topic. Las secciones vacías se ocultan solas (por eso hoy solo se ven Recientes y Off-Topic).
- **Presupuesto vivo**: techo mensual = base (60 €) + donaciones del mes, con **techo duro absoluto de 200 €**; diario = techo/días del mes (hoy: 60/31 ≈ 1,94 €/día, y así lo muestra el banner). Alertas críticas por email a ADMIN_ALERT_EMAIL con anti-spam de 6 h.
- **Donaciones**: página pública `/donaciones/` (PayPal + Bizum + objetivo con contador) y pestaña del panel `/panel/donaciones/` para registrarlas a mano. **PENDIENTE: tus datos reales de PayPal (y Bizum ONG cuando exista la asociación).**
- **API pública v1 de solo lectura** (CC-BY-SA): `/api/v1/claims/` y `/api/v1/claims/<slug>/` — ya visible en producción.
- **Login con email O nickname** y **verificación de email** con enlace firmado (72 h) y reenvío.
- **Superusuario por `.env`** (`manage.py ensure_superuser` con ADMIN_EMAIL/ADMIN_PASSWORD): se acabaron las contraseñas por chat. **La contraseña actual está en el `.env` de cada entorno** (`sudo cat /opt/isthistrue/.env` como root); cámbiala cuando quieras ahí y re-ejecuta el comando.
- `/panel/` ahora redirige a Códigos (adiós al 404), plantillas legales de asociación en `docs/asociacion/`, y el warning de deprecación de Celery arreglado.

## Errores y particularidades del proceso

1. **Bug en el ZIP (arreglado por mí)**: en `docker-compose.yml` el comentario del puerto quedó DENTRO de la cadena: `"127.0.0.1:8090:8000  # 8080 lo ocupa ntfy..."`. Docker no habría arrancado. Movido fuera de la cadena y commiteado con la fase.
2. **La IA de desarrollo conservó los 5 fixes anteriores** (puerto 8090, `forum_local`, `machina.urls`, `related_name`, `config/__init__` y hasta el `VectorExtension`): el protocolo de ZIPs del CLAUDE.md funcionó.
3. **CI sigue sin poder subirse**: reintenté el push de `ci.yml` y GitHub volvió a rechazarlo (el token sigue solo con scope `repo`). El portero volvió a ser la suite de tests en el VPS: verde antes de espejo y producción.
4. **Sin tests nuevos**: la Fase 3 no añade ni un test (siguen siendo los 10 del robot). Presupuesto vivo, API, verificación de email y donaciones están sin cobertura — se lo dejo señalado a la IA de desarrollo en docs/06.
5. **Migración nueva**: solo `analysis.0002` (topic + tags en Post). Generada, commiteada y aplicada en espejo y producción sin incidencias.
6. **Curiosidad del espejo**: el banner marcaba "Hoy: 0,08/1,94 €" — el modo simulado registra un gasto ficticio en la contabilidad local (BD del espejo, no gasta nada real). Cosmético; anotado para la IA de desarrollo.
7. **stagings.xyztserver.com**: confirmado que ya resuelve al VPS; certificado emitido y HTTPS activo. El alias `staging` se mantiene como tolerado (CLAUDE.md). Con el espejo apagado verás 502: es lo esperado.
8. Los `.env` de producción y espejo tienen ahora `ADMIN_EMAIL` (tu gmail) y `ADMIN_PASSWORD` (generada fuerte, no impresa en ningún chat ni log).

## Ritual seguido

ZIP → temporal → rsync sin `--delete` (migraciones commiteadas intactas) → `git diff` revisado → commit+push a main (`b6dbf80`, `f170704`) → tests 10/10 en espejo → checklist espejo (login por email, portada, donaciones, API, panel, foro, wiki, RSS: todo 200 y contenido correcto) → espejo apagado → producción: down → `.bak` con fecha → pull → up --build → migrate → collectstatic → ensure_superuser → verificación HTTPS externa.

## PENDIENTE DAVID (actualizado)

1. **Token GitHub con scope `repo`+`workflow`** (única pieza que falta del ritual completo).
2. **Claves del `.env`**: ANTHROPIC_API_KEY (+MOCK_AGENTS=false), Turnstile, Brevo (¡ahora más importante: sin SMTP los emails de verificación de cuenta salen solo por consola!), HF_TOKEN.
3. **Datos de donaciones**: enlace PayPal real y objetivo, desde el panel.
4. Permisos del foro machina en /admin/ (sigue pendiente del checklist 2A).
5. Backups restic B10 (VIM3 + VPN + rclone interactivo, contigo).
6. fail2ban: confirmar que lo quieres activo.
