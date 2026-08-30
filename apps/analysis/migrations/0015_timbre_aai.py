from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('analysis', '0014_libro_de_cuentas')]
    operations = [
        migrations.AddField('post', 'aai_job_id',
                            models.CharField(blank=True, default='',
                                             max_length=64)),
    ]
