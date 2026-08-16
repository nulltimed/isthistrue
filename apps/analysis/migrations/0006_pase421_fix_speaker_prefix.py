# Pase 4.2.1 I7: reparacion de datos — el bug 'SPEAKER_SPEAKER_00' (doble prefijo)
# en segmentos y propuestas de nombre existentes. La causa (diarization.py) queda
# corregida en codigo; esta migracion limpia lo ya guardado en produccion.
from django.db import migrations


def fix_double_prefix(apps, schema_editor):
    TranscriptSegment = apps.get_model('analysis', 'TranscriptSegment')
    for seg in TranscriptSegment.objects.filter(speaker_label__startswith='SPEAKER_SPEAKER_'):
        seg.speaker_label = seg.speaker_label.replace('SPEAKER_SPEAKER_', 'SPEAKER_', 1)
        seg.save(update_fields=['speaker_label'])
    SpeakerNameProposal = apps.get_model('wiki', 'SpeakerNameProposal')
    for prop in SpeakerNameProposal.objects.filter(speaker_label__startswith='SPEAKER_SPEAKER_'):
        prop.speaker_label = prop.speaker_label.replace('SPEAKER_SPEAKER_', 'SPEAKER_', 1)
        prop.save(update_fields=['speaker_label'])


class Migration(migrations.Migration):
    dependencies = [('analysis', '0005_pase42_h_segmentvote_opus'), ('wiki', '0002_claim_sources_ok')]
    operations = [migrations.RunPython(fix_double_prefix, migrations.RunPython.noop)]
