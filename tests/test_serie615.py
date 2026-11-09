"""Serie 6.15 (2026-11-09): toda tarea debe EXISTIR para el worker.

Cazado en producción (log del worker, 09-11, 07:21): «Received unregistered
task of type 'apps.forum.moderation.resolve_expired_warnings' ... The message
has been ignored and discarded». Celery autodiscover solo importa el tasks.py
de cada app; las tareas definidas en otros módulos (forum/moderation.py,
agents/batch.py) no se registraban en el worker y sus mensajes se tiraban en
silencio: ni advertencias de 48 h, ni triaje de moderación del foro. El CI no
podía verlo porque ALWAYS_EAGER ejecuta en línea, en el proceso que ya había
importado el módulo. Es la regla del 6.11 otra vez: lo que solo falla EN
CALIENTE necesita un candado estructural que lo simule en frío.

Este candado hace exactamente lo que hace el worker al arrancar
(import_default_modules) y comprueba que:
 1. cada @shared_task definida bajo apps/ queda registrada, y
 2. cada entrada del beat_schedule apunta a una tarea registrada.
Si alguien vuelve a definir una tarea fuera de un tasks.py (o de algo que un
tasks.py importe), el CI se pone rojo antes de que producción la descarte.
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from config.celery import app

RAIZ = Path(__file__).resolve().parent.parent


def _tareas_definidas():
    """Barrido AST de apps/: nombres de toda funcion decorada con shared_task."""
    tareas = []
    for f in sorted((RAIZ / 'apps').rglob('*.py')):
        if '__pycache__' in f.parts or 'migrations' in f.parts:
            continue
        arbol = ast.parse(f.read_text(encoding='utf-8'))
        modulo = '.'.join(f.relative_to(RAIZ).with_suffix('').parts)
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in nodo.decorator_list:
                base = dec.func if isinstance(dec, ast.Call) else dec
                nombre = getattr(base, 'id', None) or getattr(base, 'attr', '')
                if nombre != 'shared_task':
                    continue
                custom = None
                if isinstance(dec, ast.Call):
                    for kw in dec.keywords:
                        if kw.arg == 'name' and isinstance(kw.value, ast.Constant):
                            custom = kw.value.value
                tareas.append(custom or f'{modulo}.{nodo.name}')
    return tareas


class TodaTareaRegistradaEnElWorker(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Lo mismo que hace el worker al arrancar: importar el tasks.py de
        # cada app instalada. Sin los puentes de la 6.15, aqui faltan tareas.
        app.loader.import_default_modules()

    def test_toda_shared_task_de_apps_esta_registrada(self):
        definidas = _tareas_definidas()
        self.assertGreaterEqual(len(definidas), 5, 'el barrido AST no vio nada')
        for t in definidas:
            self.assertIn(t, app.tasks,
                          f'{t} esta definida pero el worker NO la registra: '
                          f'muevela a un tasks.py o importala desde uno '
                          f'(puente 6.15) — en produccion sus mensajes se '
                          f'descartan en silencio')

    def test_todo_el_beat_apunta_a_tareas_registradas(self):
        for clave, entrada in app.conf.beat_schedule.items():
            self.assertIn(entrada['task'], app.tasks,
                          f'beat «{clave}» programa {entrada["task"]}, que el '
                          f'worker no conoce: el mensaje se descartaria cada vez')
