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
    'budget_base_eur': '100',
    'budget_hard_ceiling_eur': '200',
    'paypal_url': '',
    'opus_rescan_percent': '40',
    'opus_rescan_min_users': '50',
    'opus_rescan_percent': '40',
    'donation_goal_eur': '100',
    # 4.2 D4 — Trending (propuesta pactada con David; ajustable sin tocar codigo):
    'trending_votes_threshold': '5',
    'trending_window_days': '7',
    # 4.2 H5/H1 (editables por mods y superusuario en su panel):
    'segment_opus_downvotes': '5',
    'message_sensitive_reports': '5',
    # 4.3-A.1 K6: puerta del registro (1 abierto / 0 cerrado), toggle del panel
    'registration_open': '1',
    'lang_es': '1', 'lang_en': '1',
}

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for k, v in DEFAULTS.items():
            SystemSetting.objects.get_or_create(key=k, defaults={'value': v})
        self.stdout.write(self.style.SUCCESS('Umbrales sembrados.'))
