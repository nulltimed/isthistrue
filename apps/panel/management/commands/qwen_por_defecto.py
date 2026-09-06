"""5.2-A (orden expresa de David, 2026-09-06): «la familia Qwen3 para todo,
Claude de respaldo». Este comando aplica esa orden a las ruedas YA GIRADAS del
panel (la trampa del 4.4-G: una fila vieja pinaria Claude en silencio):

  - cada model_<tarea> con un Claude pasa a su equivalente Qwen por escalon
  - el Claude que tenia queda guardado como model_fb_<tarea> (el respaldo)

Reversible al completo desde /panel/modelos/ — las ruedas siguen siendo de
David. Idempotente: una fila ya en Qwen no se toca.
"""
from django.core.management.base import BaseCommand

from apps.agents import catalog
from apps.panel.models import SystemSetting

EQUIVALENTE = {1: 'qwen3.8-flash', 2: 'qwen3.7-plus',
               3: 'qwen3.8-max', 4: 'qwen3.8-max', 5: 'qwen3.8-max'}


class Command(BaseCommand):
    help = 'Pasa las ruedas del panel a Qwen y guarda el Claude previo como respaldo.'

    def handle(self, *args, **opts):
        for tarea in catalog.TASK_KEYS:
            fila = SystemSetting.objects.filter(key=f'model_{tarea}').first()
            if not fila or not fila.value.startswith('claude'):
                continue
            previo = fila.value
            nuevo = EQUIVALENTE.get(catalog.tier(previo), 'qwen3.7-plus')
            SystemSetting.objects.update_or_create(
                key=f'model_fb_{tarea}', defaults={'value': previo})
            fila.value = nuevo
            fila.save(update_fields=['value'])
            self.stdout.write(f'{tarea}: {previo} -> {nuevo} (respaldo: {previo})')
        self.stdout.write('hecho')
