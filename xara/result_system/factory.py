import random
import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice, FuzzyDecimal
from django.utils import timezone
import factory.fuzzy
from .models import (
    School, SystemSettings, AcademicYear, Class, Subject, ClassSubject,
    User, Teacher, TeacherSubject, Student, StudentDocument, StudentSubject,
    Exam, GradeSheet, SubjectGrade, ClassStatistics, OverallStatistics,
    GeneralExam, GeneralExamWeight, GeneralExamGradeSheet, GeneralExamSubjectGrade,
    GeneralExamClassStatistics, GeneralExamOverallStatistics
)
from decimal import Decimal
from factory import LazyAttribute
from factory.fuzzy import FuzzyDecimal





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
    year = factory.Sequence(lambda n: f"{2023+n}-{2024+n}")
    start_date = factory.Faker('date_between', start_date='-1y', end_date='today')
    end_date = factory.LazyAttribute(lambda o: o.start_date + timezone.timedelta(days=365))
    is_current = factory.Faker('boolean', chance_of_getting_true=25)

class ClassFactory(DjangoModelFactory):
    class Meta:
        model = Class

    school = factory.SubFactory(SchoolFactory)
    name = factory.Sequence(lambda n: f'Class {n}')
    academic_year = factory.SubFactory(AcademicYearFactory)
    capacity = factory.Faker('random_int', min=20, max=40)
    class_master = factory.LazyFunction(lambda: Teacher.objects.order_by('?').first())

class SubjectFactory(DjangoModelFactory):
    class Meta:
        model = Subject

    school = factory.SubFactory(SchoolFactory)
    name = factory.Faker('word')
    code = factory.Sequence(lambda n: f'SUB{n:03}')
    default_credit = FuzzyDecimal(0.5, 5.0)
    description = factory.Faker('text', max_nb_chars=200)
    subject_type = FuzzyChoice(['MANDATORY', 'ELECTIVE'])
    is_active = factory.Faker('boolean', chance_of_getting_true=90)

class ClassSubjectFactory(DjangoModelFactory):
    class Meta:
        model = ClassSubject

    class_obj = factory.SubFactory(ClassFactory)
    subject = factory.SubFactory(SubjectFactory)
    credit = factory.SelfAttribute('subject.default_credit')
    max_students = factory.LazyAttribute(lambda o: o.class_obj.capacity)
    is_active = factory.Faker('boolean', chance_of_getting_true=90)

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    school = factory.SubFactory(SchoolFactory)
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
        django_get_or_create = ('teacher', 'subject', 'class_obj')

    teacher = factory.SubFactory(TeacherFactory)
    subject = factory.SubFactory(SubjectFactory)
    class_obj = factory.SubFactory(ClassFactory)
    assigned_date = factory.Faker('date_this_year')

class StudentFactory(DjangoModelFactory):
    class Meta:
        model = Student

    school = factory.SubFactory(SchoolFactory)
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    matricula_code = factory.Sequence(lambda n: f'STD{n:06}')
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
    is_active = factory.Faker('boolean', chance_of_getting_true=90)
    results_access_payed = factory.Faker('boolean', chance_of_getting_true=50)
    results_access_date_payed = factory.LazyFunction(lambda: timezone.now().date() if random.choice([True, False]) else None)
    results_access_phone_number_payed = factory.Faker('phone_number')


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
        django_get_or_create = ('student', 'class_subject', 'academic_year')

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


class GradeSheetFactory(DjangoModelFactory):
    class Meta:
        model = GradeSheet

    student = factory.SubFactory(StudentFactory)
    exam = factory.SubFactory(ExamFactory)
    class_obj = factory.SelfAttribute('student.current_class')
    academic_year = factory.SelfAttribute('exam.academic_year')
    total_score = FuzzyDecimal(0, 100)
    credits_attempted = FuzzyDecimal(10, 30)
    
    credits_obtained = LazyAttribute(lambda o: 
        Decimal(min(
            float(o.credits_attempted),  # Use credits_attempted directly
            float(FuzzyDecimal(0, 30).evaluate(0, None, None))  # Directly evaluate the FuzzyDecimal
        )).quantize(Decimal('0.01'))
    )
    
    average = FuzzyDecimal(0, 20)
    remark = LazyAttribute(lambda o: 'PASSED' if float(o.average) >= 10 else 'FAILED')
    rank = factory.Faker('random_int', min=1, max=50)




class SubjectGradeFactory(DjangoModelFactory):
    class Meta:
        model = SubjectGrade

    grade_sheet = factory.SubFactory(GradeSheetFactory)
    class_subject = factory.SubFactory(ClassSubjectFactory)
    score = FuzzyDecimal(0, 20)
    rank = factory.Faker('random_int', min=1, max=50)
    exam_taken = factory.Faker('boolean', chance_of_getting_true=95)
    observation = factory.Faker('sentence')

class ClassStatisticsFactory(DjangoModelFactory):
    class Meta:
        model = ClassStatistics

    exam = factory.SubFactory(ExamFactory)
    class_obj = factory.SubFactory(ClassFactory)
    class_subject = factory.SubFactory(ClassSubjectFactory)
    academic_year = factory.SelfAttribute('exam.academic_year')
    max_score = FuzzyDecimal(15, 20)
    min_score = FuzzyDecimal(0, 10)
    avg_score = FuzzyDecimal(10, 15)
    num_sat = factory.Faker('random_int', min=10, max=40)
    num_passed = factory.LazyAttribute(lambda o: random.randint(0, o.num_sat))
    percentage_passed = factory.LazyAttribute(lambda o: (o.num_passed / o.num_sat) * 100 if o.num_sat > 0 else 0)

class OverallStatisticsFactory(DjangoModelFactory):
    class Meta:
        model = OverallStatistics

    exam = factory.SubFactory(ExamFactory)
    class_obj = factory.SubFactory(ClassFactory)
    academic_year = factory.SelfAttribute('exam.academic_year')
    num_students = factory.Faker('random_int', min=20, max=100)
    num_passes = factory.LazyAttribute(lambda o: random.randint(0, o.num_students))
    class_average = FuzzyDecimal(5, 15)
    overall_percentage_pass = factory.LazyAttribute(lambda o: (o.num_passes / o.num_students) * 100 if o.num_students > 0 else 0)

class GeneralExamFactory(DjangoModelFactory):
    class Meta:
        model = GeneralExam

    school = factory.SubFactory(SchoolFactory)
    name = factory.Sequence(lambda n: f'General Exam {n}')
    academic_year = factory.SubFactory(AcademicYearFactory)
    start_date = factory.LazyFunction(timezone.now)
    end_date = factory.LazyAttribute(lambda o: o.start_date + timezone.timedelta(days=14))
    total_coefficient = FuzzyDecimal(1, 5)

class GeneralExamWeightFactory(DjangoModelFactory):
    class Meta:
        model = GeneralExamWeight

    general_exam = factory.SubFactory(GeneralExamFactory)
    exam = factory.SubFactory(ExamFactory)
    weight = FuzzyDecimal(0.1, 1)

class GeneralExamGradeSheetFactory(DjangoModelFactory):
    class Meta:
        model = GeneralExamGradeSheet

    student = factory.SubFactory(StudentFactory)
    general_exam = factory.SubFactory(GeneralExamFactory)
    class_obj = factory.SelfAttribute('student.current_class')
    academic_year = factory.SelfAttribute('general_exam.academic_year')
    total_score = FuzzyDecimal(0, 100)
    average = FuzzyDecimal(0, 20)
    rank = factory.Faker('random_int', min=1, max=50)
    remark = factory.LazyAttribute(lambda o: 'PASSED' if o.average >= 10 else 'FAILED')

class GeneralExamSubjectGradeFactory(DjangoModelFactory):
    class Meta:
        model = GeneralExamSubjectGrade

    grade_sheet = factory.SubFactory(GeneralExamGradeSheetFactory)
    class_subject = factory.SubFactory(ClassSubjectFactory)
    calculated_score = FuzzyDecimal(0, 20)
    rank = factory.Faker('random_int', min=1, max=50)
    observation = factory.Faker('sentence')

class GeneralExamClassStatisticsFactory(DjangoModelFactory):
    class Meta:
        model = GeneralExamClassStatistics

    general_exam = factory.SubFactory(GeneralExamFactory)
    class_obj = factory.SubFactory(ClassFactory)
    class_subject = factory.SubFactory(ClassSubjectFactory)
    max_score = FuzzyDecimal(15, 20)
    min_score = FuzzyDecimal(0, 10)
    avg_score = FuzzyDecimal(10, 15)
    num_students = factory.Faker('random_int', min=10, max=40)
    num_passed = factory.LazyAttribute(lambda o: random.randint(0, o.num_students))
    percentage_passed = factory.LazyAttribute(lambda o: (o.num_passed / o.num_students) * 100 if o.num_students > 0 else 0)

class GeneralExamOverallStatisticsFactory(DjangoModelFactory):
    class Meta:
        model = GeneralExamOverallStatistics

    general_exam = factory.SubFactory(GeneralExamFactory)
    class_obj = factory.SubFactory(ClassFactory)
    num_students = factory.Faker('random_int', min=20, max=100)
    num_passes = factory.LazyAttribute(lambda o: random.randint(0, o.num_students))
    class_average = FuzzyDecimal(5, 15)
    overall_percentage_pass = factory.LazyAttribute(lambda o: (o.num_passes / o.num_students) * 100 if o.num_students > 0 else 0)