from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('analysis', '0013_frases_inocuas')]
    operations = [
        migrations.CreateModel(
            name='CostEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('provider', models.CharField(max_length=20)),
                ('concept', models.CharField(max_length=40)),
                ('eur', models.DecimalField(decimal_places=4, max_digits=8)),
                ('created_at', models.DateTimeField(auto_now_add=True,
                                                    db_index=True)),
                ('post', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='costs', to='analysis.post')),
            ],
        ),
    ]
