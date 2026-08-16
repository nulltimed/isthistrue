# Pase 4.3-A.1 K3 (decision de David): purga de los candidatos AUTOMATICOS de
# nombre (OCR/contexto) no confirmados — producian basura tipo creditos de
# edicion. Los propuestos por usuarios y los confirmados se conservan.
from django.db import migrations


def purge_auto_candidates(apps, schema_editor):
    SpeakerNameProposal = apps.get_model('wiki', 'SpeakerNameProposal')
    SpeakerNameProposal.objects.exclude(source='user').filter(confirmed=False).delete()


class Migration(migrations.Migration):
    dependencies = [('analysis', '0006_pase421_fix_speaker_prefix')]
    operations = [migrations.RunPython(purge_auto_candidates, migrations.RunPython.noop)]
