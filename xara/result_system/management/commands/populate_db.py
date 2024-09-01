from django.core.management.base import BaseCommand
from django.db import transaction
from result_system.factory import (
    SchoolFactory, SystemSettingsFactory, AcademicYearFactory, ClassFactory,
    SubjectFactory, ClassSubjectFactory, UserFactory, TeacherFactory,
    TeacherSubjectFactory, StudentFactory, StudentDocumentFactory,
    StudentSubjectFactory, ExamFactory, GeneralExamFactory, ResultFactory,
    AttendanceFactory, ReportCardFactory, AttendanceReportFactory
)
import random
from datetime import timedelta
from django.utils import timezone
from result_system.models import ClassSubject, Student, Attendance

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
            for subject in random.sample(subjects, k=random.randint(5, 8)):
                ClassSubjectFactory(class_obj=class_obj, subject=subject)

        # Create Teachers and assign subjects, ensuring uniqueness
        teachers = TeacherFactory.create_batch(20, user__school=school)
        for teacher in teachers:
            assigned_subjects = set()
            for _ in range(random.randint(1, 3)):
                while True:
                    class_subject = random.choice(ClassSubject.objects.filter(class_obj__school=teacher.user.school))
                    if (teacher, class_subject.subject, class_subject.class_obj) not in assigned_subjects:
                        assigned_subjects.add((teacher, class_subject.subject, class_subject.class_obj))
                        TeacherSubjectFactory(teacher=teacher, subject=class_subject.subject, class_obj=class_subject.class_obj)
                        break

        # Create Students and enroll in subjects
        for class_obj in classes:
            students = StudentFactory.create_batch(
                random.randint(15, 30),
                current_class=class_obj,
                school=school  # Ensure school is set correctly
            )
            for student in students:
                StudentDocumentFactory(student=student)
                for class_subject in ClassSubject.objects.filter(class_obj=class_obj):
                    if not class_subject.is_full():
                        StudentSubjectFactory(student=student, class_subject=class_subject)
                    else:
                        self.stdout.write(f'Skipped enrollment for {student} in {class_subject.subject.name} because the class is full.')

        # Create Exams and GeneralExams
        exams = ExamFactory.create_batch(3, school=school, academic_year=current_year)
        GeneralExamFactory(school=school, academic_year=current_year, exams=exams)

        # Create Results
        for student in Student.objects.filter(school=school):
            for class_subject in student.current_class.subjects.all():
                for exam in exams:
                    ResultFactory(
                        student=student,
                        class_subject=class_subject,
                        exam=exam,
                        created_by=random.choice(teachers).user
                    )

        # Create Attendance records, ensuring no duplicates
        for student in Student.objects.filter(school=school):
            for class_subject in student.current_class.subjects.all():
                for day in range(50):  # Assume 50 school days
                    attendance_date = timezone.now().date() - timedelta(days=day)
                    if not Attendance.objects.filter(student=student, class_subject=class_subject, date=attendance_date).exists():
                        AttendanceFactory(student=student, class_subject=class_subject, date=attendance_date)
                    else:
                        self.stdout.write(f'Skipped attendance record for {student} on {attendance_date} because it already exists.')

        # Generate ReportCards and AttendanceReports
        for student in Student.objects.filter(school=school):
            report_card = ReportCardFactory(student=student, academic_year=current_year)
            report_card.generate()
            report_card.calculate_class_rank()

            attendance_report = AttendanceReportFactory(student=student, academic_year=current_year)
            attendance_report.generate()

        self.stdout.write(f'Completed ecosystem for school: {school.name}')
