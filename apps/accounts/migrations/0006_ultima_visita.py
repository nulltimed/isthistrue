# 5.1-B.1: el login anterior, para que «Novedades en tus seguidos» tenga una
# marca real (Django pisa last_login en el propio login).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_pase44a_idioma'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='previous_login',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
