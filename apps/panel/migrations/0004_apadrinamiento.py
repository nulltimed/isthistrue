# 5.13-C: la donacion de apadrinamiento queda atada a su post.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('panel', '0003_donacion_verificada'),
        ('analysis', '0020_relojes_por_palabra'),
    ]

    operations = [
        migrations.AddField(
            model_name='donation',
            name='post',
            field=models.ForeignKey(blank=True, null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='sponsorships', to='analysis.post'),
        ),
    ]
