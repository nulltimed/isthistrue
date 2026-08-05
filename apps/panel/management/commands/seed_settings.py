"""Siembra los umbrales por defecto (ejecutar tras migrate)."""
from django.core.management.base import BaseCommand
from apps.panel.models import SystemSetting

DEFAULTS = {
    'opinion_ratio_percent': '70',
    'minutes_per_factual_claim': '5',
    'votes_to_validate': '5',
    'votes_to_rescue': '10',
    'validation_window_days': '3',
    'startup_mode_min_users': '50',
    'mod_vote_weight': '5',
    'name_confirm_points': '5',
    'donation_goal_eur': '50',
    'lang_es': '1', 'lang_en': '1',
}

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for k, v in DEFAULTS.items():
            SystemSetting.objects.get_or_create(key=k, defaults={'value': v})
        self.stdout.write(self.style.SUCCESS('Umbrales sembrados.'))
