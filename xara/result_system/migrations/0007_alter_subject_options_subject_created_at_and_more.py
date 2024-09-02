# Generated by Django 5.1 on 2024-09-02 12:43

import datetime
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('result_system', '0006_student_is_active'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='subject',
            options={'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='subject',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=datetime.datetime(2024, 9, 2, 12, 43, 5, 419302, tzinfo=datetime.timezone.utc)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='subject',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='subject',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='subject',
            name='default_credit',
            field=models.DecimalField(decimal_places=1, default=1.0, max_digits=3, validators=[django.core.validators.MinValueValidator(1.0), django.core.validators.MaxValueValidator(20.0)]),
        ),
    ]
