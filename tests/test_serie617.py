"""Serie 6.17 (orden de David, 2026-11-09, 12:32: «sí, y actualízalo y avísame
de ello cada vez que sea necesario»): desplegar.sh — el despliegue en UN comando.

Candados: el script existe, su sintaxis es valida (bash -n), y conserva los
pasos que los candados historicos exigen — freno de analisis en vuelo (4.4-F),
up --build -d SIN down (orden 2026-09-09), migrate, seed_settings, smoke de
estaticos (candado 2026-08-13), chequeo de «unregistered» (6.15), reinicio de
beat si el pull toca config/celery.py (leccion 4.3) y el patron main()+exec
que le permite auto-actualizarse en mitad de un pull sin romperse.
"""
import subprocess
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / 'desplegar.sh'


class ScriptDeDespliegue(SimpleTestCase):
    def test_existe_y_su_sintaxis_es_valida(self):
        self.assertTrue(SCRIPT.exists(), 'desplegar.sh no esta en la raiz del repo')
        r = subprocess.run(['bash', '-n', str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f'sintaxis rota: {r.stderr}')

    def test_conserva_los_pasos_que_exigen_los_candados(self):
        s = SCRIPT.read_text(encoding='utf-8')
        for trozo, motivo in (
            ("CHEAP_RUNNING','FULL_RUNNING", 'freno de analisis en vuelo (4.4-F)'),
            ('up --build -d', 'levantar sin down (orden 2026-09-09)'),
            ('manage.py migrate', 'migraciones'),
            ('seed_settings', 'ajustes nuevos'),
            ('collectstatic --noinput', 'estaticos'),
            ('main.css', 'smoke test de estaticos (candado 2026-08-13)'),
            ('unregistered', 'tareas fantasma (candado 6.15)'),
            ('config/celery.py', 'reinicio de beat (leccion 4.3)'),
            ('main "$@"', 'patron main(): bash lee el fichero entero'),
        ):
            self.assertIn(trozo, s, f'desplegar.sh perdio: {motivo}')
        self.assertNotIn('compose down', s, 'el down esta prohibido (2026-09-09)')
