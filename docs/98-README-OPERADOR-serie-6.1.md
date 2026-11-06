# SERIE 6.1 — README del operador (que esta vez es David en persona)

**De:** Fable web (canal reactivado por David esta noche) · **Fecha:** 2026-11-06
**Un solo parche** (orden literal de David: «Aplica todos los cambios absolutamente en un
solo parche»). Si algo sale mal: `git revert` del commit de la serie y redesplegar.

## Qué trae
1. **Donaciones y apadrinamiento RETIRADOS del producto** (Lectura A): fuera el banner de
   donar, la página /donaciones/ (redirige a /creditos/) y el botón de apadrinar. El
   backend PayPal (IPN/retorno) queda vivo por los enlaces antiguos; el modelo Donation
   queda como libro interno de financiación.
2. **Créditos de la SL**: monedero + libro (`accounts.CreditWallet/CreditLedger`), página
   /creditos/, adelantar análisis (cola o votos) a 1 crédito por 20 min, compra APAGADA
   (`sl_checkout_enabled=0`) hasta que la SL exista. El superusuario no gasta.
3. **Rastreo de origen**: cadena de difusión del claim hasta el origen más antiguo
   documentado; automático en rojos/ámbar, 1 crédito bajo demanda en verdes/grises;
   visual en la ficha del claim.
4. Ajustes nuevos en Panel → Ajustes (grupo 6.1) · 3 migraciones (accounts/0007,
   wiki/0011, panel/0006) · tests `tests/test_serie61.py` · README y CLAUDE.md enmendados.

## Comandos EXACTOS para aplicar en el VPS (en este orden)

```bash
# 0) Entrar y comprobar que el CI del commit está EN VERDE en
#    https://github.com/nulltimed/isthistrue/actions — CI rojo = NO desplegar.

# 1) ¿Hay análisis en vuelo? (si devuelve algo, espera a que terminen)
cd /opt/isthistrue && sudo -u i docker compose exec web python manage.py shell -c \
"from apps.analysis.models import Post; print(list(Post.objects.filter(status__in=['CHEAP_RUNNING','FULL_RUNNING']).values_list('pk', flat=True)))"

# 2) ESPEJO primero (MOCK, no gasta): probar la serie entera
cd /opt/isthistrue-staging && sudo -u i git pull
sudo -u i docker compose -f docker-compose.staging.yml -p staging up --build -d
sudo -u i docker compose -f docker-compose.staging.yml -p staging exec web python manage.py migrate
sudo -u i docker compose -f docker-compose.staging.yml -p staging exec web python manage.py seed_settings
sudo -u i docker compose -f docker-compose.staging.yml -p staging exec web python manage.py test tests --settings=tests.settings_test
# Mirar con el navegador en el espejo: /creditos/, un post en cola, una ficha de claim.
sudo -u i docker compose -f docker-compose.staging.yml -p staging down

# 3) PRODUCCIÓN (ritual sin down, orden tuya del 2026-09-09)
cd /opt/isthistrue
sudo -u i cp .env /home/d/env-backup-$(date +%Y%m%d).bak   # por costumbre; el parche no toca .env
sudo -u i git pull
sudo -u i docker compose up --build -d
sudo -u i docker compose exec web python manage.py migrate
sudo -u i docker compose exec web python manage.py seed_settings
sudo -u i docker compose exec web python manage.py collectstatic --noinput
sudo -u i docker compose restart beat   # costumbre tras cada serie; esta no toca celery.py

# 4) CANDADO DE ESTÁTICOS (obligatorio, en cada dominio)
for d in isthistrue.xyztserver.com escierto.xyztserver.com wikitrue.xyztserver.com; do
  curl -s -o /dev/null -w "$d CSS: %{http_code} %{size_download} bytes\n" https://$d/static/css/main.css
done

# 5) Humo de la serie (con la web privada, entra como d y comprueba):
#    /creditos/ carga con packs en «Próximamente» · /donaciones/ redirige ·
#    el banner ya no dice «Faltan» ni «Donar» · un claim ROJO nuevo trae
#    «¿De dónde viene?» tras su próximo análisis.
```

## Avisos
- `seed_settings` siembra las claves nuevas SIN pisar tu panel (sin --force).
- Presupuesto y panel de modelos: NI TOCADOS (tus ruedas mandan, como siempre).
- El rastreo automático añade ~0,04 €/claim rojo/ámbar al gasto de cada análisis
  (fusible incluido). Se apaga en Panel → Ajustes → «Rastreo de origen automático».
- Pendiente para encender cobros: SL constituida + pasarela (Stripe recomendado) +
  contrato David↔SL. Hasta entonces `sl_checkout_enabled` sigue en 0 y la web privada.
