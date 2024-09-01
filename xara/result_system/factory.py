import random
import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice, FuzzyDecimal
from django.utils import timezone
from .models import (
    School, SystemSettings, AcademicYear, Class, Subject, ClassSubject,
    User, Teacher, TeacherSubject, Student, StudentDocument, StudentSubject,
    Exam, GeneralExam, Result, Attendance, ReportCard, AttendanceReport
)

class SchoolFactory(DjangoModelFactory):
    class Meta:
        model = School

    name = factory.Faker('company')
    code = factory.Sequence(lambda n: f'SCH{n:03}')
    address = factory.Faker('address')
    phone = factory.Faker('phone_number')
    email = factory.Faker('company_email')
    website = factory.Faker('url')

class SystemSettingsFactory(DjangoModelFactory):
    class Meta:
        model = SystemSettings

    school = factory.SubFactory(SchoolFactory)
    school_initials = factory.LazyAttribute(lambda o: o.school.name[:3].upper())
    academic_year_format = "YYYY-YYYY"
    max_students_per_class = factory.Faker('random_int', min=20, max=40)
    grading_system = {
        "A": {"min": 16, "max": 20, "description": "Excellent"},
        "B": {"min": 14, "max": 15.99, "description": "Very Good"},
        "C": {"min": 12, "max": 13.99, "description": "Good"},
        "D": {"min": 10, "max": 11.99, "description": "Average"},
        "E": {"min": 0, "max": 9.99, "description": "Fail"}
    }
    default_pass_mark = 10.00

class AcademicYearFactory(DjangoModelFactory):
    class Meta:
        model = AcademicYear

    school = factory.SubFactory(SchoolFactory)
    year = factory.Faker('year')
    start_date = factory.Faker('date_this_year', before_today=True, after_today=False)
    end_date = factory.Faker('date_this_year', before_today=False, after_today=True)
    is_current = factory.Faker('boolean', chance_of_getting_true=25)

class ClassFactory(DjangoModelFactory):
    class Meta:
        model = Class

    school = factory.SubFactory(SchoolFactory)
    name = factory.Sequence(lambda n: f'Class {n}')
    academic_year = factory.SubFactory(AcademicYearFactory)
    capacity = factory.Faker('random_int', min=20, max=40)

class SubjectFactory(DjangoModelFactory):
    class Meta:
        model = Subject

    school = factory.SubFactory(SchoolFactory)
    name = factory.Faker('word')
    code = factory.Sequence(lambda n: f'SUB{n:03}')
    default_credit = FuzzyDecimal(0.5, 5.0)
    description = factory.Faker('text', max_nb_chars=200)
    subject_type = FuzzyChoice(['MANDATORY', 'ELECTIVE'])

class ClassSubjectFactory(DjangoModelFactory):
    class Meta:
        model = ClassSubject

    class_obj = factory.SubFactory(ClassFactory)
    subject = factory.SubFactory(SubjectFactory)
    credit = factory.SelfAttribute('subject.default_credit')
    max_students = factory.SelfAttribute('class_obj.capacity')

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Faker('user_name')
    email = factory.Faker('email')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    phone = factory.Faker('phone_number')
    user_type = FuzzyChoice(['S', 'T'])

class TeacherFactory(DjangoModelFactory):
    class Meta:
        model = Teacher

    user = factory.SubFactory(UserFactory, user_type='T')
    qualifications = factory.Faker('text', max_nb_chars=200)
    date_joined = factory.Faker('date_this_decade')

class TeacherSubjectFactory(DjangoModelFactory):
    class Meta:
        model = TeacherSubject

    teacher = factory.SubFactory(TeacherFactory)
    subject = factory.SubFactory(SubjectFactory)
    class_obj = factory.SubFactory(ClassFactory)
    assigned_date = factory.Faker('date_this_year')

class StudentFactory(DjangoModelFactory):
    class Meta:
        model = Student

    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    current_class = factory.SubFactory(ClassFactory)
    date_of_birth = factory.Faker('date_of_birth', minimum_age=10, maximum_age=20)
    gender = FuzzyChoice(['M', 'F', 'O'])
    address = factory.Faker('address')
    email = factory.Faker('email')
    phone = factory.Faker('phone_number')
    parent_name = factory.Faker('name')
    parent_contact = factory.Faker('phone_number')
    parent_email = factory.Faker('email')
    parent_address = factory.Faker('address')
    date_enrolled = factory.Faker('date_this_decade')

class StudentDocumentFactory(DjangoModelFactory):
    class Meta:
        model = StudentDocument

    student = factory.SubFactory(StudentFactory)
    document_type = FuzzyChoice(['BIRTH_CERT', 'ID_CARD', 'PREV_REPORT', 'OTHER'])
    file = factory.django.FileField(filename='document.pdf')
    description = factory.Faker('sentence')

class StudentSubjectFactory(DjangoModelFactory):
    class Meta:
        model = StudentSubject

    student = factory.SubFactory(StudentFactory)
    class_subject = factory.SubFactory(ClassSubjectFactory)
    academic_year = factory.SelfAttribute('class_subject.class_obj.academic_year')
    enrollment_date = factory.Faker('date_this_year')
    is_active = factory.Faker('boolean', chance_of_getting_true=90)

class ExamFactory(DjangoModelFactory):
    class Meta:
        model = Exam

    school = factory.SubFactory(SchoolFactory)
    name = factory.Sequence(lambda n: f'Exam {n}')
    academic_year = factory.SubFactory(AcademicYearFactory)
    start_date = factory.LazyFunction(timezone.now)
    end_date = factory.LazyAttribute(lambda o: o.start_date + timezone.timedelta(days=7))
    is_active = factory.Faker('boolean', chance_of_getting_true=50)
    max_score = 20.00

class GeneralExamFactory(DjangoModelFactory):
    class Meta:
        model = GeneralExam

    school = factory.SubFactory(SchoolFactory)
    name = factory.Sequence(lambda n: f'General Exam {n}')
    academic_year = factory.SubFactory(AcademicYearFactory)
    start_date = factory.LazyFunction(timezone.now)
    end_date = factory.LazyAttribute(lambda o: o.start_date + timezone.timedelta(days=14))

    @factory.post_generation
    def exams(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for exam in extracted:
                self.exams.add(exam)
        else:
            for _ in range(3):
                self.exams.add(ExamFactory(school=self.school, academic_year=self.academic_year))

class ResultFactory(DjangoModelFactory):
    class Meta:
        model = Result

    student = factory.SubFactory(StudentFactory)
    class_subject = factory.SubFactory(ClassSubjectFactory)
    exam = factory.SubFactory(ExamFactory)
    mark = FuzzyDecimal(0, 20, precision=2)
    created_by = factory.SubFactory(UserFactory, user_type='T')
    comments = factory.Faker('paragraph')

class AttendanceFactory(DjangoModelFactory):
    class Meta:
        model = Attendance

    student = factory.SubFactory(StudentFactory)
    class_subject = factory.SubFactory(ClassSubjectFactory)
    date = factory.Faker('date_this_year')
    is_present = factory.Faker('boolean', chance_of_getting_true=90)
    reason = factory.LazyAttribute(lambda o: factory.Faker('sentence') if not o.is_present else '')

class ReportCardFactory(DjangoModelFactory):
    class Meta:
        model = ReportCard

    student = factory.SubFactory(StudentFactory)
    academic_year = factory.SubFactory(AcademicYearFactory)
    total_average = FuzzyDecimal(0, 20, precision=2)
    class_rank = factory.Faker('random_int', min=1, max=50)
    comments = factory.Faker('paragraph')

class AttendanceReportFactory(DjangoModelFactory):
    class Meta:
        model = AttendanceReport

    student = factory.SubFactory(StudentFactory)
    academic_year = factory.SubFactory(AcademicYearFactory)
    total_days = factory.Faker('random_int', min=150, max=200)
    days_present = factory.LazyAttribute(lambda o: random.randint(0, o.total_days))
    days_absent = factory.LazyAttribute(lambda o: o.total_days - o.days_present)
    attendance_percentage = factory.LazyAttribute(lambda o: (o.days_present / o.total_days) * 100 if o.total_days > 0 else 0)
