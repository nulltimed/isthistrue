from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('analysis', '0012_pase44i_atribucion_incierta')]
    operations = [
        migrations.CreateModel(
            name='InnocuousPhrase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('text_norm', models.CharField(max_length=200, unique=True)),
                ('times_seen', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('first_post', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='analysis.post')),
            ],
        ),
    ]
