# 5.3-C: las opiniones tambien se analizan (por su logica); el campo kind
# distingue en la wiki que es afirmacion verificada y que es opinion analizada.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wiki', '0007_pase44c_modelo_usado'),
    ]

    operations = [
        migrations.AddField(
            model_name='claim',
            name='kind',
            field=models.CharField(choices=[('FACTUAL', 'Afirmación'),
                                            ('OPINION', 'Opinión')],
                                   default='FACTUAL', max_length=8),
        ),
    ]
