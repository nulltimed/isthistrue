"""Serie 6.11 (2026-11-09): el 500 de la llave inglesa en produccion.

kombu (el mensajero de Celery) venia sin fijar en requirements.txt; una
reconstruccion de imagen instalo kombu 5.6, que exige redis-py >=6.1, con
redis==5.* fijado: TODO `.delay()` moria con VersionMismatch y el primer
sintoma visible fue un 500 al relanzar una etapa. El CI nunca lo cazo porque
CELERY_TASK_ALWAYS_EAGER no toca el broker, y los comandos de backfill corren
en linea. Candado: esta comprobacion replica la regla de compatibilidad que
kombu aplica al abrir el canal — si las versiones instaladas vuelven a
desparejarse, el CI se pone rojo ANTES de que lo haga produccion.
"""
from django.test import SimpleTestCase


class MensajeroYRedisCompatibles(SimpleTestCase):
    def test_kombu_y_redis_py_estan_emparejados(self):
        import kombu
        import redis
        kombu_v = tuple(int(x) for x in kombu.__version__.split('.')[:2])
        redis_v = tuple(redis.VERSION[:2])
        if kombu_v >= (5, 6):
            # kombu 5.6+ rechaza redis-py < 6.1 en el transporte Redis
            # (kombu/transport/redis.py: VersionMismatch).
            self.assertGreaterEqual(
                redis_v, (6, 1),
                f'kombu {kombu.__version__} exige redis-py >=6.1 y hay '
                f'{redis.__version__}: todo .delay() morira en produccion. '
                'Emparejar los pines en requirements.txt (leccion 6.11).')
        else:
            # La pareja fijada que funciona: kombu 5.5 con redis-py 5.x.
            self.assertGreaterEqual(redis_v, (4, 5))

    def test_el_transporte_redis_de_kombu_importa(self):
        # El import ya ejecuta el modulo donde vive el chequeo de version:
        # si kombu cambiara el contrato de forma incompatible, esto chilla.
        from kombu.transport import redis as transporte
        self.assertTrue(hasattr(transporte, 'Transport'))
