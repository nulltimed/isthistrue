# Altas de servicios (todo va al .env; David rellena)
1. **Anthropic** (console.anthropic.com): cuenta de API separada del Claude Pro. Cargar 50 €. **Fijar límite mensual en el panel de la consola = doble airbag** (además del corte a 200 € del código). Pegar la clave en `ANTHROPIC_API_KEY` y poner `MOCK_AGENTS=false`.
2. **Cloudflare Turnstile**: solo Turnstile (el DNS sigue en IONOS). Site key + secret al .env.
3. **Brevo**: SMTP (300/día gratis). Añadir registros DKIM/DMARC en el DNS de IONOS. El Postfix personal NO se toca.
4. ~~Telegram~~: DESCARTADO para siempre (decisión de David). Las alertas van por email Brevo a ADMIN_ALERT_EMAIL.
5. **GitHub**: repo `nulltimed/isthistrue`, AGPL-3.0 (mini-guía de Git ya entregada; verifica `.gitignore` con `.env` ANTES del primer push).
6. **PayPal/Bizum**: enlace PayPal + número Bizum mostrado (Fase 3, panel Donaciones).
