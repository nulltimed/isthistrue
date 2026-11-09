#!/usr/bin/env bash
# desplegar.sh — Serie 6.17 (orden de David, 2026-11-09): desplegar con UN comando.
#
# Uso:   cd /opt/isthistrue && bash desplegar.sh
#        bash desplegar.sh --forzar   -> salta el freno de analisis en vuelo
#                                        (solo si sabes lo que haces: mata la tarea)
#
# Hace, en orden y parando al primer fallo: freno de analisis en vuelo ->
# git pull -> up --build -d (sin down, orden 2026-09-09) -> migrate ->
# seed_settings -> collectstatic + smoke de estaticos -> salud del worker
# (candados 6.11 y 6.15). Si el pull toca config/celery.py, reinicia beat solo
# (leccion 4.3). Si el pull actualiza ESTE script, se relanza con la version
# nueva automaticamente. REGLA 6.17: cada vez que Claude cambie este script,
# lo avisa en el informe.
#
# Todo va envuelto en main() para que bash lea el fichero ENTERO antes de
# ejecutar: asi el pull puede cambiar el script sin romper la ejecucion en curso.

main() {
set -u
cd /opt/isthistrue || { echo "ERROR: no existe /opt/isthistrue"; exit 1; }

echo "== 1/7 Freno: ¿analisis en vuelo? =="
VUELO=$(sudo -u i docker compose exec -T web python manage.py shell -c "from apps.analysis.models import Post; print(list(Post.objects.filter(status__in=['CHEAP_RUNNING','FULL_RUNNING']).values_list('pk', flat=True)))" 2>/dev/null | tail -1)
echo "   En vuelo: ${VUELO:-sin respuesta}"
if [ "${1:-}" != "--forzar" ] && [ "$VUELO" != "[]" ]; then
  echo "PARADO: hay analisis en vuelo (recrear el worker los mataria, 4.4-F)."
  echo "Espera a que terminen, o repite con:  bash desplegar.sh --forzar"
  exit 1
fi

echo "== 2/7 git pull =="
ANTES=$(sudo -u i git rev-parse HEAD)
sudo -u i git pull || exit 1
AHORA=$(sudo -u i git rev-parse HEAD)
CAMBIADOS=$(sudo -u i git diff --name-only "$ANTES" "$AHORA")

# Si el pull actualizo ESTE script, relanzarse con la version nueva (una vez).
if echo "$CAMBIADOS" | grep -q '^desplegar.sh$' && [ "${DESPLEGAR_REEXEC:-}" != "1" ]; then
  echo "   El propio script de despliegue se actualizo: continuo con la version nueva."
  DESPLEGAR_REEXEC=1 exec bash desplegar.sh "$@"
fi

echo "== 3/7 Levantar (up --build -d, SIN down: orden 2026-09-09) =="
sudo -u i docker compose up --build -d || exit 1

# Leccion 4.3: beat lee su calendario al arrancar y no recarga en caliente.
if echo "$CAMBIADOS" | grep -q '^config/celery.py$'; then
  echo "   (el pull toco config/celery.py: reiniciando beat)"
  sudo -u i docker compose restart beat
fi

echo "== 4/7 Migraciones =="
sudo -u i docker compose exec -T web python manage.py migrate || exit 1

echo "== 5/7 Ajustes nuevos (seed_settings, idempotente) =="
sudo -u i docker compose exec -T web python manage.py seed_settings || exit 1

echo "== 6/7 Estaticos + smoke test (candado 2026-08-13) =="
sudo -u i docker compose exec -T web python manage.py collectstatic --noinput >/dev/null || exit 1
CSS_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://esestocierto.com/static/css/main.css)
CSS_BYTES=$(curl -s -o /dev/null -w "%{size_download}" https://esestocierto.com/static/css/main.css)
echo "   CSS: $CSS_CODE $CSS_BYTES bytes"
if [ "$CSS_CODE" != "200" ] || [ "${CSS_BYTES:-0}" -lt 5000 ]; then
  echo "ROJO: el CSS no sirve (un despliegue feo es un despliegue ROTO)."
  echo "Prueba: sudo -u i docker compose restart web   y repite el script."
  exit 1
fi

echo "== 7/7 Salud del worker (candados 6.11 y 6.15) =="
sleep 5
if sudo -u i docker compose logs worker --since 2m 2>/dev/null | grep -qi unregistered; then
  echo "ROJO: el worker descarta tareas (unregistered) — avisar a Claude con este log:"
  sudo -u i docker compose logs worker --tail=20
  exit 1
fi
sudo -u i docker compose logs worker --tail=3
echo
echo "✅ DESPLIEGUE COMPLETO ($ANTES -> $AHORA)."
exit 0
}
main "$@"
