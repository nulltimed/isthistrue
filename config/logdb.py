"""5.23-H (orden de David): los logs del sistema, a la base de datos.

Un `logging.Handler` que duplica en `panel.SystemLog` cada registro de nivel
INFO o superior que ya sale por la consola del contenedor. Asi el panel puede
enseñar, filtrar, copiar y limpiar lo que hasta hoy solo se veia con
`docker compose logs` desde SSH.

Reglas de higiene (un logger que rompe la web es peor que ninguno):
- jamas lanza: cualquier fallo (BD caida, tabla sin migrar, transaccion rota)
  se traga en silencio y el registro sigue saliendo por consola;
- no se escucha a si mismo ni a los loggers de la propia BD (bucle infinito);
- reentrada bloqueada por hilo (si al guardar se emite otro log, se ignora);
- el ROL del contenedor sale de ISTT_ROLE (docker-compose) o se deduce de la
  linea de comandos (celery worker / beat / gunicorn-manage).
"""
import logging
import os
import sys
import threading

_local = threading.local()
_IGNORAR = ('django.db', 'config.logdb', 'psycopg', 'urllib3', 'httpcore',
            'asyncio', 'PIL', 'faker', 'multipart', 'markdown', 'kombu', 'amqp')


def role():
    r = os.environ.get('ISTT_ROLE', '').strip().lower()
    if r in ('web', 'worker', 'beat'):
        return r
    argv = ' '.join(sys.argv).lower()
    if 'celery' in argv and 'beat' in argv:
        return 'beat'
    if 'celery' in argv and 'worker' in argv:
        return 'worker'
    if 'gunicorn' in argv or 'runserver' in argv or 'manage.py' in argv:
        return 'web'
    return 'other'


class DBLogHandler(logging.Handler):
    def emit(self, record):
        if getattr(_local, 'dentro', False):
            return
        if record.name.startswith(_IGNORAR):
            return
        _local.dentro = True
        try:
            from django.apps import apps
            if not apps.ready:
                return
            from apps.panel.models import SystemLog
            try:
                mensaje = self.format(record) if self.formatter else record.getMessage()
            except Exception:
                mensaje = str(record.msg)
            if record.exc_info and record.exc_text:
                mensaje = f'{mensaje}\n{record.exc_text}'
            post_id = None
            try:
                from apps.analysis import costs
                p = costs.current_post()
                post_id = p.pk if p is not None else None
            except Exception:
                post_id = None
            SystemLog.objects.create(level=record.levelname[:10], logger=record.name[:80],
                                     role=role(), message=mensaje[:20000], post_id=post_id)
        except Exception:
            pass   # regla de oro: el log jamas tumba nada
        finally:
            _local.dentro = False
