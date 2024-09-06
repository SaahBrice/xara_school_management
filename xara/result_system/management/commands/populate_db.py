from django.core.management.base import BaseCommand
from django.db import transaction
from result_system.factory import (
    SchoolFactory, SystemSettingsFactory, AcademicYearFactory, ClassFactory,
    SubjectFactory, ClassSubjectFactory, UserFactory, TeacherFactory,
    TeacherSubjectFactory, StudentFactory, StudentDocumentFactory,
    StudentSubjectFactory, ExamFactory, GradeSheetFactory, SubjectGradeFactory,
    ClassStatisticsFactory, OverallStatisticsFactory, GeneralExamFactory,
    GeneralExamWeightFactory, GeneralExamGradeSheetFactory, GeneralExamSubjectGradeFactory,
    GeneralExamClassStatisticsFactory, GeneralExamOverallStatisticsFactory
)
import random
from factory import Iterator, SubFactory, LazyAttribute, Faker
from result_system.models import ClassStatistics, ClassSubject, GeneralExamClassStatistics, GeneralExamGradeSheet, GeneralExamOverallStatistics, GeneralExamSubjectGrade, GeneralExamWeight, OverallStatistics, Student
from decimal import Decimal
from factory import LazyAttribute
from factory.fuzzy import FuzzyDecimal

class Command(BaseCommand):
    help = 'Populate database with sample data'

    def add_arguments(self, parser):
        parser.add_argument('--schools', type=int, default=1, help='Number of schools to create')

    @transaction.atomic
    def handle(self, *args, **options):
        num_schools = options['schools']

        for _ in range(num_schools):
            self.create_school_ecosystem()

        self.stdout.write(self.style.SUCCESS(f'Successfully created {num_schools} school ecosystems'))

    def create_school_ecosystem(self):
        # Create School and SystemSettings
        school = SchoolFactory()
        SystemSettingsFactory(school=school)
        self.stdout.write(f'Created school: {school.name}')

        # Create AcademicYears
        current_year = AcademicYearFactory(school=school, is_current=True)
        prev_year = AcademicYearFactory(school=school, is_current=False)

        # Create Classes
        classes = ClassFactory.create_batch(7, school=school, academic_year=current_year)

        # Create Subjects
        subjects = SubjectFactory.create_batch(10, school=school)

        # Create ClassSubjects
        for class_obj in classes:
            subject_count = random.randint(5, 8)
            class_subjects = ClassSubjectFactory.create_batch(
                subject_count,
                class_obj=class_obj,
                subject=Iterator(random.sample(subjects, k=subject_count))
            )

        # Create Teachers and assign subjects
        teachers = TeacherFactory.create_batch(20, user__school=school)
        for teacher in teachers:
            for _ in range(random.randint(1, 3)):
                class_subject = random.choice(ClassSubject.objects.filter(class_obj__school=school))
                TeacherSubjectFactory(
                    teacher=teacher, 
                    subject=class_subject.subject, 
                    class_obj=class_subject.class_obj
                )

        # Create Students and enroll in subjects
        for class_obj in classes:
            student_count = min(random.randint(15, 30), class_obj.capacity)
            students = StudentFactory.create_batch(
                student_count,
                school=school,
                current_class=class_obj
            )
            class_subjects = ClassSubject.objects.filter(class_obj=class_obj)
            for student in students:
                StudentDocumentFactory(student=student)
                for class_subject in class_subjects:
                    current_count = class_subject.get_current_student_count()
                    self.stdout.write(f"Enrolling in subject: {class_subject.subject.name}, Current Count: {current_count}/{class_subject.max_students}")
                    # Only enroll if subject is not full
                    if not class_subject.is_full():
                        StudentSubjectFactory(
                            student=student,
                            class_subject=class_subject,
                            academic_year=current_year
                        )
                    else:
                        self.stdout.write(f"Class {class_obj} subject {class_subject.subject} is full")

        # Create Exams
        exams = ExamFactory.create_batch(3, school=school, academic_year=current_year)

        # Create GradeSheets and SubjectGrades
        students = Student.objects.filter(school=school)
        for exam in exams:
            for student in students:
                grade_sheet = GradeSheetFactory(student=student, exam=exam, class_obj=student.current_class, academic_year=current_year)
                for class_subject in student.current_class.subjects.all():
                    SubjectGradeFactory(grade_sheet=grade_sheet, class_subject=class_subject)

        for exam in exams:
            for class_obj in classes:
                for class_subject in class_obj.subjects.all():
                    # Check if the ClassStatistics entry already exists
                    ClassStatistics.objects.get_or_create(
                        exam=exam, 
                        class_obj=class_obj, 
                        class_subject=class_subject, 
                        academic_year=current_year,
                        defaults={
                            'max_score': FuzzyDecimal(15, 20).fuzz(),
                            'min_score': FuzzyDecimal(0, 10).fuzz(),
                            'avg_score': FuzzyDecimal(10, 15).fuzz(),
                            'num_sat': random.randint(10, 40),
                            'num_passed': random.randint(0, 40),
                            'percentage_passed': (random.randint(0, 40) / 40) * 100
                        }
                    )
                
                # Check if the OverallStatistics entry already exists
                OverallStatistics.objects.get_or_create(
                    exam=exam,
                    class_obj=class_obj,
                    academic_year=current_year,
                    defaults={
                        'num_students': random.randint(20, 100),
                        'num_passes': random.randint(0, 100),
                        'class_average': FuzzyDecimal(5, 15).fuzz(),
                        'overall_percentage_pass': (random.randint(0, 100) / 100) * 100
                    }
                )

        # Create GeneralExam
        general_exam = GeneralExamFactory(school=school, academic_year=current_year)
        for exam in exams:
            GeneralExamWeight.objects.get_or_create(
                general_exam=general_exam, 
                exam=exam,
                defaults={'weight': FuzzyDecimal(0.1, 1).fuzz()}
            )

        # Create GeneralExamGradeSheets and GeneralExamSubjectGrades
        for student in students:
            general_exam_grade_sheet, _ = GeneralExamGradeSheet.objects.get_or_create(
                student=student,
                general_exam=general_exam,
                class_obj=student.current_class,
                academic_year=current_year,
                defaults={
                    'total_score': FuzzyDecimal(0, 100).fuzz(),
                    'average': FuzzyDecimal(0, 20).fuzz(),
                    'rank': random.randint(1, 50),
                    'remark': 'PASSED' if random.uniform(0, 20) >= 10 else 'FAILED'
                }
            )


            # Create GeneralExamSubjectGrades for each class_subject
            for class_subject in student.current_class.subjects.all():
                GeneralExamSubjectGrade.objects.get_or_create(
                    grade_sheet=general_exam_grade_sheet, 
                    class_subject=class_subject,
                    defaults={
                        'calculated_score': FuzzyDecimal(0, 20).fuzz(),
                        'rank': random.randint(1, 50),
                        'observation': 'Good'  # Adjust as needed
                    }
                )

        # Create GeneralExamClassStatistics and GeneralExamOverallStatistics
        for class_obj in classes:
            # Create GeneralExamClassStatistics for each class_subject
            for class_subject in class_obj.subjects.all():
                GeneralExamClassStatistics.objects.get_or_create(
                    general_exam=general_exam, 
                    class_obj=class_obj, 
                    class_subject=class_subject,
                    defaults={
                        'max_score': FuzzyDecimal(15, 20).fuzz(),
                        'min_score': FuzzyDecimal(0, 10).fuzz(),
                        'avg_score': FuzzyDecimal(10, 15).fuzz(),
                        'num_students': random.randint(10, 40),
                        'num_passed': random.randint(0, 40),
                        'percentage_passed': (random.randint(0, 40) / 40) * 100
                    }
                )

            # Create GeneralExamOverallStatistics for each class_obj
            GeneralExamOverallStatistics.objects.get_or_create(
                general_exam=general_exam,
                class_obj=class_obj,
                defaults={
                    'num_students': random.randint(20, 100),
                    'num_passes': random.randint(0, 100),
                    'class_average': FuzzyDecimal(5, 15).fuzz(),
                    'overall_percentage_pass': (random.randint(0, 100) / 100) * 100
                }
            )

        self.stdout.write(f'Completed ecosystem for school: {school.name}')