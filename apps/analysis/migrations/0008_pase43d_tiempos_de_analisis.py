"""4.3-D: tiempos del analisis, para que medir un video largo sea REPETIBLE.

Peticion del operador (docs/33 C2): "AnalysisRequest no guarda tiempos de inicio
ni fin: Fable deberia anadirlos para que la medicion sea repetible y no un
experimento suelto".

Van en Post y no en AnalysisRequest a proposito: AnalysisRequest es "quien pulso
Analizar" y hay una por solicitante; el analisis ocurre UNA vez por post. Poner
el reloj en la solicitud daria N relojes para un solo cronometraje.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('analysis', '0007_pase43a1_purga_candidatos_auto')]

    operations = [
        migrations.AddField(model_name='post', name='cheap_started_at',
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='post', name='cheap_finished_at',
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='post', name='full_started_at',
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='post', name='full_finished_at',
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='post', name='transcribe_seconds',
                            field=models.FloatField(default=0.0)),
        migrations.AddField(model_name='post', name='diarize_seconds',
                            field=models.FloatField(default=0.0)),
    ]
