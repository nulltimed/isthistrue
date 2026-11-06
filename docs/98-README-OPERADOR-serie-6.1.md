# SERIES 6.1 → 6.3 — Guía CONSOLIDADA del operador (David en persona)

**De:** Fable web · **Fecha:** 2026-11-06 · **Commit de despliegue:** `0616a74` (CI verde)
**Todo se despliega DE UNA VEZ** (orden de David). Marcha atrás: `git revert` de la serie que moleste.

## Qué trae el paquete

| Serie | Qué |
|---|---|
| 6.1 a-e | Donaciones RETIRADAS (Lectura A) · créditos (1=1 €) con página /creditos/ y compra APAGADA · adelantar análisis por tramos de 20 min · rastreo de origen (auto en rojos/ámbar, 1 crédito bajo demanda) con eslabón torcido resaltado · brújula 🧭 en el foro · segundo superusuario (socio) por `.env` |
| 6.1-f | Aviso previo con cifra y saldo en TODO gasto · reanálisis profundo de pago (2 créditos/frase, una vez por frase, se paga la revisión y no el resultado) · reembolsos automáticos (rastreo sin resultado al momento; adelantos FAILED a diario por beat) |
| 6.2 | API de lectura con clave X-API-Key (claims/ficha/análisis/transcripción/canales/stats, sobre {data, meta, attribution} CC-BY-SA) · solicitud pública con escrutinio por IA (exclusiones: partidos y organismos contra la esencia) · reclamación → bandeja · pestaña API del panel · la API keyless antigua queda retirada |
| 6.3 | Registro en DOS CARRILES (físicas sin investigar; jurídicas con escrutinio; denegación reclamable → bandeja) · elección Gratuita/Pro (Pro «Próximamente» hasta la SL) · badge «Verificado» embebible (iframe de una línea) · dossieres B2B con enlace secreto, exentos del candado privado · huecos de la SL sembrados vacíos |

## Despliegue (en orden; espejo primero si quieres el ritual completo)

```bash
# 0) CI en VERDE confirmado para 0616a74 (ya verificado por Fable web).

# 1) ¿Análisis en vuelo?
cd /opt/isthistrue && sudo -u i docker compose exec web python manage.py shell -c \
"from apps.analysis.models import Post; print(list(Post.objects.filter(status__in=['CHEAP_RUNNING','FULL_RUNNING']).values_list('pk', flat=True)))"

# 2) .env de producción: añade (con tus valores) ANTES de levantar
#    ADMIN2_USERNAME=  ADMIN2_EMAIL=  ADMIN2_PASSWORD=     (la cuenta del socio)
#    SITE_URL=https://esestocierto.com                      (enlaces de los correos)

# 3) Producción (ritual sin down)
sudo -u i git pull
sudo -u i docker compose up --build -d
sudo -u i docker compose exec web python manage.py migrate
#   -> aplicará: accounts/0007, 0008, 0009 · wiki/0011 · panel/0006, 0007 · api/0001
sudo -u i docker compose exec web python manage.py seed_settings
sudo -u i docker compose exec web python manage.py collectstatic --noinput
sudo -u i docker compose restart beat      # ¡OBLIGATORIO!: 6.1-f añadió tarea a beat

# 4) Candado de estáticos
for d in isthistrue.xyztserver.com escierto.xyztserver.com wikitrue.xyztserver.com; do
  curl -s -o /dev/null -w "$d CSS: %{http_code} %{size_download} bytes\n" https://$d/static/css/main.css
done
```

## Humo (entrando como d; la web sigue privada)
- `/creditos/` con packs 5/10/20 en «Próximamente» · `/donaciones/` redirige · banner sin «Faltan» ni «Donar».
- `/api/` carga SIN pasar el candado privado (documentación + solicitud); `/api/v1/claims/` sin cabecera → 401 JSON.
- `/panel/api/`: tres bandejas (registros, claves, dossieres) vacías + formulario de dossier.
- `/accounts/register/`: selector física/jurídica + elección Gratuita/Pro («Próximamente»).
- Una ficha de claim: caja «📋 Insertar en tu web» y su `/embed/` sirviendo el badge.
- Crear un dossier de prueba con un post: su enlace abre la página profesional aunque la web esté privada; revocar → 404.
- Los botones que gastan créditos piden confirmación con la cifra.

## Avisos
- Presupuesto y panel de modelos: NI TOCADOS.
- Correos (clave API, denegaciones, dossieres): salen por el email del `.env` (Brevo); sin credenciales quedan en el log — los enlaces también se muestran en pantalla, nada bloquea.
- El rastreo automático añade ~0,04 €/claim rojo/ámbar (fusible y apagable en Panel → Ajustes).
- Pendiente del paquete «constitución» (cuando David dé los datos de la SL): Stripe (packs + Pro), aviso legal y privacidad con la SL, encender sl_checkout_enabled.
