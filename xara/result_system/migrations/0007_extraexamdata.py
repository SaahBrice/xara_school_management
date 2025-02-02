# Generated by Django 5.1 on 2024-09-17 10:31

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('result_system', '0006_alter_annualexamoverallstatistics_class_average_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtraExamData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('absences', models.PositiveIntegerField(default=0, help_text='Number of absences during the exam period.')),
                ('conduct', models.PositiveIntegerField(choices=[(5, 'Excellent'), (4, 'Very Good'), (3, 'Satisfactory'), (2, 'Unsatisfactory'), (1, 'Poor')], help_text='Conduct rating: 1 = Poor, to 5 = Excellent')),
                ('human_investment', models.PositiveIntegerField(choices=[(5, 'Excellent'), (4, 'Very Good'), (3, 'Satisfactory'), (2, 'Unsatisfactory'), (1, 'Poor')], help_text='Human investment rating: 1 = Poor, to 5 = Excellent')),
                ('fees_owed', models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Amount of fees owed in CFA.', max_digits=10)),
                ('participation_in_extracurricular', models.BooleanField(default=False, help_text='Did the student participate in extracurricular activities?')),
                ('remarks', models.TextField(blank=True, help_text='General remarks or observations by teachers.')),
                ('academic_year', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_exam_data', to='result_system.academicyear')),
                ('class_obj', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_exam_data', to='result_system.class')),
                ('general_exam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_exam_data', to='result_system.generalexam')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_exam_data', to='result_system.student')),
            ],
            options={
                'verbose_name_plural': 'Extra Exam Data',
                'unique_together': {('academic_year', 'class_obj', 'general_exam', 'student')},
            },
        ),
    ]
