# Generated by Django 5.1 on 2024-09-16 18:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('result_system', '0003_generalexamclassstatistics_academic_year_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='generalexamclassstatistics',
            name='avg_score',
            field=models.DecimalField(decimal_places=2, max_digits=4, null=True),
        ),
        migrations.AlterField(
            model_name='generalexamclassstatistics',
            name='max_score',
            field=models.DecimalField(decimal_places=2, max_digits=4, null=True),
        ),
        migrations.AlterField(
            model_name='generalexamclassstatistics',
            name='min_score',
            field=models.DecimalField(decimal_places=2, max_digits=4, null=True),
        ),
        migrations.AlterField(
            model_name='generalexamclassstatistics',
            name='num_passed',
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='generalexamclassstatistics',
            name='num_students',
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name='generalexamclassstatistics',
            name='percentage_passed',
            field=models.DecimalField(decimal_places=2, max_digits=5, null=True),
        ),
    ]
