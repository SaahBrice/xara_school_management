from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Avg, Max, Min, Count, Sum, Q, F, ExpressionWrapper, DecimalField, Case, When
from django.utils.text import Truncator
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.core.cache import cache
from decimal import Decimal




class GradeCalculationError(Exception):
    """Exception raised for errors in grade calculations."""
    pass

class GradeCreationError(Exception):
    """Exception raised for errors in grade creation or update."""
    pass

class RankCalculationError(Exception):
    """Exception raised for errors in rank calculation or update."""
    pass



def validate_file_size(value):
    filesize = value.size
    if filesize > 5 * 1024 * 1024:  # 5MB
        raise ValidationError("The maximum file size that can be uploaded is 5MB")

class School(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=10, unique=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class SystemSettings(models.Model):
    school = models.OneToOneField(School, on_delete=models.CASCADE, related_name='settings')
    school_initials = models.CharField(max_length=10, help_text="Used for generating student codes")
    academic_year_format = models.CharField(max_length=20, default="YYYY-YYYY", help_text="Format for academic year")
    max_students_per_class = models.PositiveIntegerField(default=3000)
    grading_system = models.JSONField(
        default=dict,
        help_text="""
        JSON representation of the grading system. Example:
        {
            "A": {"min": 16, "max": 20, "description": "Excellent"},
            "B": {"min": 14, "max": 15.99, "description": "Very Good"},
            "C": {"min": 12, "max": 13.99, "description": "Good"},
            "D": {"min": 10, "max": 11.99, "description": "Average"},
            "E": {"min": 0, "max": 9.99, "description": "Fail"}
        }
        """
    )
    default_pass_mark = models.DecimalField(max_digits=4, decimal_places=2, default=10.00)

    def __str__(self):
        return f"System Settings for {self.school.name}"

class AcademicYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='academic_years')
    year = models.CharField(max_length=9)  # e.g., "2023-2024"
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        unique_together = ('school', 'year')
        indexes = [
            models.Index(fields=['school', 'is_current']),
        ]

    def __str__(self):
        return f"{self.school.name} - {self.year}"

class Class(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='classes')
    name = models.CharField(max_length=50)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='classes')
    capacity = models.PositiveIntegerField(default=3000)
    class_master = models.ForeignKey(
        'Teacher',  # Assuming you have a Teacher model
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mastered_classes'
    )

    class Meta:
        unique_together = ('school', 'name', 'academic_year')
        verbose_name_plural = 'Classes'

    def __str__(self):
        return f"{self.name} - {self.academic_year.year}"

    def get_active_subjects(self):
        return self.subjects.filter(is_active=True)

    def get_current_student_count(self):
        return self.current_students.count()

    def is_full(self):
        return self.get_current_student_count() >= self.capacity

    def get_class_master_name(self):
        return self.class_master.user.get_full_name() if self.class_master else "Not Assigned"



class Subject(models.Model):
    SUBJECT_TYPES = [
        ('MANDATORY', 'Mandatory'),
        ('ELECTIVE', 'Elective'),
    ]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    default_credit = models.DecimalField(max_digits=3, decimal_places=1, default=1.0, validators=[MinValueValidator(1.0), MaxValueValidator(20.0)])
    description = models.TextField(blank=True)
    subject_type = models.CharField(max_length=10, choices=SUBJECT_TYPES, default='MANDATORY')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def truncated_description(self):
        return Truncator(self.description).chars(15)

    class Meta:
        unique_together = ('school', 'code')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


    def toggle_active(self):
        self.is_active = not self.is_active
        self.save()

    def get_classes(self):
        return self.classes.filter(class_obj__academic_year__is_current=True)


class ClassSubject(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='classes')
    credit = models.DecimalField(max_digits=3, decimal_places=1)
    max_students = models.PositiveIntegerField(default=0, help_text="0 means no limit")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('class_obj', 'subject')

    def __str__(self):
        return f"{self.class_obj} - {self.subject}"

    def save(self, *args, **kwargs):
        if not self.credit:
            self.credit = self.subject.default_credit
        if not self.max_students:
            self.max_students = self.class_obj.capacity
        super().save(*args, **kwargs)

    def get_current_student_count(self):
        # Count only active enrollments
        return self.student_subjects.filter(is_active=True).count()


    def is_full(self):
        return self.max_students > 0 and self.get_current_student_count() >= self.max_students

class User(AbstractUser):
    SECRETARY = 'S'
    TEACHER = 'T'
    USER_TYPE_CHOICES = [
        (SECRETARY, _('Secretary')),
        (TEACHER, _('Teacher')),
    ]
    user_type = models.CharField(max_length=1, choices=USER_TYPE_CHOICES)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='users', null=True, blank=True) 
    phone = models.CharField(max_length=20, blank=True)

    def toggle_active(self):
        self.is_active = not self.is_active
        self.save()

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_user_type_display()})"

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    qualifications = models.TextField(blank=True)
    date_joined = models.DateField(default=timezone.now)

    def truncated_qualifications(self):
        return Truncator(self.qualifications).chars(15)

    def __str__(self):
        return self.user.get_full_name()

class TeacherSubject(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='teaching_assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE)
    assigned_date = models.DateField(default=timezone.now)

    def truncated_qualifications(self):
        return Truncator(self.qualifications).chars(15)

    class Meta:
        unique_together = ('teacher', 'subject', 'class_obj')

    def __str__(self):
        return f"{self.teacher} - {self.subject} ({self.class_obj})"


def generate_matricula_code(student):
    school_initials = student.school.settings.school_initials
    year = student.date_enrolled.year % 100
    class_code = student.current_class.name[:2].upper()
    last_student = Student.objects.filter(
        school=student.school,
        matricula_code__startswith=f"{school_initials}{year}{class_code}"
    ).order_by('matricula_code').last()
    
    if last_student:
        last_number = int(last_student.matricula_code[-2:])
        new_number = last_number + 1
    else:
        new_number = 1
    
    return f"{school_initials}{year}{class_code}{new_number:02d}"


class StudentManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related('current_class')


class Student(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='students')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    matricula_code = models.CharField(max_length=15, unique=True)
    current_class = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True, related_name='current_students')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], blank=True)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    parent_name = models.CharField(max_length=200, blank=True)
    parent_contact = models.CharField(max_length=20, blank=True)
    parent_email = models.EmailField(blank=True)
    parent_address = models.TextField(blank=True)
    date_enrolled = models.DateField(default=timezone.now)
    picture = models.ImageField(upload_to='student_pictures/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    results_access_payed = models.BooleanField(default=False)
    results_access_date_payed = models.DateField(null=True, blank=True)
    results_access_phone_number_payed = models.CharField(max_length=20, blank=True)
    objects = StudentManager()

    class Meta:
        permissions = [
            ("can_view_student_grades", "Can view student grades"),
            ("can_edit_student_grades", "Can edit student grades"),
        ]
    


    def toggle_active(self):
        self.is_active = not self.is_active
        self.save()

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.matricula_code})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_class = None
        if not is_new:
            old_instance = Student.objects.get(pk=self.pk)
            old_class = old_instance.current_class

        if not self.matricula_code:
            self.matricula_code = generate_matricula_code(self)

        super().save(*args, **kwargs)

        if is_new or (self.current_class != old_class and self.current_class is not None):
            self.enroll_in_class_subjects()

    def enroll_in_class_subjects(self):
        if self.current_class:
            class_subjects = self.current_class.subjects.all()
            current_academic_year = self.current_class.academic_year
            for class_subject in class_subjects:
                try:
                    self.enroll_in_subject(class_subject, current_academic_year)
                except ValidationError:
                    # Handle the case where the class is full
                    pass

    def enroll_in_subject(self, class_subject, academic_year):
        if not class_subject.is_full():
            StudentSubject.objects.get_or_create(
                student=self,
                class_subject=class_subject,
                academic_year=academic_year,
                defaults={'is_active': True}
            )
        else:
            raise ValidationError("This subject has reached its maximum capacity for this class.")

    def unenroll_from_subject(self, class_subject, academic_year):
        StudentSubject.objects.filter(
            student=self,
            class_subject=class_subject,
            academic_year=academic_year,
            is_active=True
        ).update(is_active=False)

    def get_current_subjects(self):
        if self.current_class:
            return StudentSubject.objects.filter(
                student=self,
                academic_year=self.current_class.academic_year,
                is_active=True
            )
        return StudentSubject.objects.none()
        
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"



class StudentDocument(models.Model):
    DOCUMENT_TYPES = [
        ('BIRTH_CERT', 'Birth Certificate'),
        ('ID_CARD', 'ID Card'),
        ('PREV_REPORT', 'Previous Report Card'),
        ('OTHER', 'Other'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(
        upload_to='student_documents/',
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png']),
            validate_file_size
        ]
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student.matricula_code} - {self.get_document_type_display()}"

class StudentSubject(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrolled_subjects')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='student_subjects')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    enrollment_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('student', 'class_subject', 'academic_year')

    def __str__(self):
        return f"{self.student} - {self.class_subject.subject} ({self.academic_year})"

    def save(self, *args, **kwargs):
        if self.is_active and self.class_subject.is_full():
            raise ValidationError("This subject has reached its maximum capacity for this class.")
        super().save(*args, **kwargs)

    @classmethod
    def get_active_subjects_for_student(cls, student, academic_year):
        return cls.objects.filter(
            student=student,
            academic_year=academic_year,
            is_active=True
        ).select_related('class_subject__subject')




class Exam(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='exams')
    name = models.CharField(max_length=100)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='exams')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=False)
    max_score = models.DecimalField(max_digits=4, decimal_places=2, default=20.00)

    class Meta:
        unique_together = ('school', 'name', 'academic_year')

    def __str__(self):
        return f"{self.name} - {self.academic_year}"

    def activate(self):
        self.is_active = True
        self.save()

    def deactivate(self):
        self.is_active = False
        self.save()

    def is_ongoing(self):
        from django.utils import timezone
        now = timezone.now()
        return self.start_date <= now <= self.end_date
        



class GradeSheet(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='grade_sheets')
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='grade_sheets')
    class_obj = models.ForeignKey('Class', on_delete=models.CASCADE, related_name='grade_sheets')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='grade_sheets')
    total_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    credits_attempted = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    credits_obtained = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    average = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    remark = models.CharField(max_length=20, blank=True)
    rank = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        unique_together = ('student', 'exam', 'class_obj', 'academic_year')
        indexes = [
            models.Index(fields=['student', 'exam', 'class_obj', 'academic_year']),
            models.Index(fields=['average']),
        ]

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.exam.name} - {self.class_obj.name} - {self.academic_year}"

class SubjectGrade(models.Model):
    grade_sheet = models.ForeignKey(GradeSheet, on_delete=models.CASCADE, related_name='subject_grades')
    class_subject = models.ForeignKey('ClassSubject', on_delete=models.CASCADE, related_name='subject_grades')
    score = models.DecimalField(
        max_digits=4, 
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    rank = models.PositiveIntegerField(null=True, blank=True)
    exam_taken = models.BooleanField(default=False)
    observation = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ('grade_sheet', 'class_subject')
        indexes = [
            models.Index(fields=['grade_sheet', 'class_subject']),
            models.Index(fields=['score']),
        ]

    def __str__(self):
        status = "Taken" if self.exam_taken else "Not Taken"
        score = f"{self.score:.2f}" if self.score is not None else "N/A"
        return f"{self.grade_sheet.student.get_full_name()} - {self.class_subject.subject.name} - {status} - Score: {score}"

class ClassStatistics(models.Model):
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='class_statistics')
    class_obj = models.ForeignKey('Class', on_delete=models.CASCADE, related_name='class_statistics')
    class_subject = models.ForeignKey('ClassSubject', on_delete=models.CASCADE, related_name='class_statistics')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='class_statistics')
    max_score = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    min_score = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    avg_score = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    num_sat = models.PositiveIntegerField( null=True)
    num_passed = models.PositiveIntegerField(null=True)
    percentage_passed = models.DecimalField(max_digits=5, decimal_places=2, null=True)

    class Meta:
        unique_together = ('exam', 'class_obj', 'class_subject', 'academic_year')

    def __str__(self):
        return f"{self.class_subject.subject.name} - {self.class_obj.name} - {self.exam.name} - {self.academic_year}"

class OverallStatistics(models.Model):
    exam = models.ForeignKey('Exam', on_delete=models.CASCADE, related_name='overall_statistics')
    class_obj = models.ForeignKey('Class', on_delete=models.CASCADE, related_name='overall_statistics')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='overall_statistics')
    num_students = models.PositiveIntegerField()
    num_passes = models.PositiveIntegerField()
    class_average = models.DecimalField(max_digits=4, decimal_places=2)
    overall_percentage_pass = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('exam', 'class_obj', 'academic_year')

    def __str__(self):
        return f"Overall Stats - {self.class_obj.name} - {self.exam.name} - {self.academic_year}"







class GeneralExam(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='general_exams')
    name = models.CharField(max_length=100)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='general_exams')
    exams = models.ManyToManyField(Exam, related_name='general_exams', through='GeneralExamWeight')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    total_coefficient = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)

    class Meta:
        unique_together = ('school', 'name', 'academic_year')

    def __str__(self):
        return f"{self.name} - {self.academic_year}"


class GeneralExamWeight(models.Model):
    general_exam = models.ForeignKey(GeneralExam, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    weight = models.DecimalField(max_digits=3, decimal_places=2, default=1.00,
                                 validators=[MinValueValidator(0), MaxValueValidator(1)])

    class Meta:
        unique_together = ('general_exam', 'exam')

class GeneralExamGradeSheet(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='general_exam_grade_sheets')
    general_exam = models.ForeignKey(GeneralExam, on_delete=models.CASCADE, related_name='grade_sheets')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='general_exam_grade_sheets')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='general_exam_grade_sheets')
    credits_attempted = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    credits_obtained = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    average = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    rank = models.PositiveIntegerField(blank=True, null=True)
    remark = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = ('student', 'general_exam', 'class_obj', 'academic_year')

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.general_exam.name} - {self.class_obj.name} - {self.academic_year}"



class GeneralExamSubjectGrade(models.Model):
    grade_sheet = models.ForeignKey(GeneralExamGradeSheet, on_delete=models.CASCADE, related_name='subject_grades')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='general_exam_grades')
    calculated_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    observation = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ('grade_sheet', 'class_subject')

    def __str__(self):
        return f"{self.grade_sheet.student.get_full_name()} - {self.class_subject.subject.name} - Score: {self.calculated_score}"



class GeneralExamClassStatistics(models.Model):
    general_exam = models.ForeignKey(GeneralExam, on_delete=models.CASCADE, related_name='class_statistics')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='general_exam_class_statistics')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='general_exam_statistics')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='general_exam_class_statistics_year', null=True)
    max_score = models.DecimalField(max_digits=4, decimal_places=2,null=True)
    min_score = models.DecimalField(max_digits=4, decimal_places=2,null=True)
    avg_score = models.DecimalField(max_digits=4, decimal_places=2,null=True)
    num_students = models.PositiveIntegerField(null=True)
    num_passed = models.PositiveIntegerField(null=True)
    percentage_passed = models.DecimalField(max_digits=5, decimal_places=2,null=True)

    class Meta:
        unique_together = ('general_exam', 'class_obj', 'class_subject')

    def __str__(self):
        return f"{self.class_subject.subject.name} - {self.class_obj.name} - {self.general_exam.name}"


class GeneralExamOverallStatistics(models.Model):
    general_exam = models.ForeignKey(GeneralExam, on_delete=models.CASCADE, related_name='overall_statistics')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='general_exam_overall_statistics')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='general_exam_overall_statistics_year', null=True)
    num_students = models.PositiveIntegerField(null=True)
    num_passes = models.PositiveIntegerField(null=True)
    class_average = models.DecimalField(max_digits=4, decimal_places=2,null=True)
    overall_percentage_pass = models.DecimalField(max_digits=5, decimal_places=2,null=True)

    class Meta:
        unique_together = ('general_exam', 'class_obj')

    def __str__(self):
        return f"Overall Stats - {self.class_obj.name} - {self.general_exam.name}"








class AnnualExam(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='annual_exams')
    name = models.CharField(max_length=100, default="Annual Results")
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='annual_exams')
    general_exams = models.ManyToManyField(GeneralExam, related_name='annual_exams', through='AnnualExamWeight')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    total_coefficient = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)

    class Meta:
        unique_together = ('school', 'name', 'academic_year')

    def __str__(self):
        return f"{self.name} - {self.academic_year}"


class AnnualExamWeight(models.Model):
    annual_exam = models.ForeignKey(AnnualExam, on_delete=models.CASCADE)
    general_exam = models.ForeignKey(GeneralExam, on_delete=models.CASCADE)
    weight = models.DecimalField(max_digits=3, decimal_places=2, default=1.00,
                                 validators=[MinValueValidator(0), MaxValueValidator(1)])

    class Meta:
        unique_together = ('annual_exam', 'general_exam')

class AnnualExamGradeSheet(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='annual_exam_grade_sheets')
    annual_exam = models.ForeignKey(AnnualExam, on_delete=models.CASCADE, related_name='grade_sheets')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='annual_exam_grade_sheets')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='annual_exam_grade_sheets')
    credits_attempted = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    credits_obtained = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    average = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    rank = models.PositiveIntegerField(blank=True, null=True)
    remark = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = ('student', 'annual_exam', 'class_obj', 'academic_year')

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.annual_exam.name} - {self.class_obj.name} - {self.academic_year}"



class AnnualExamSubjectGrade(models.Model):
    grade_sheet = models.ForeignKey(AnnualExamGradeSheet, on_delete=models.CASCADE, related_name='subject_grades')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='annual_exam_grades')
    calculated_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    observation = models.CharField(max_length=50, blank=True)

    class Meta:
        unique_together = ('grade_sheet', 'class_subject')

    def __str__(self):
        return f"{self.grade_sheet.student.get_full_name()} - {self.class_subject.subject.name} - Score: {self.calculated_score}"



class AnnualExamClassStatistics(models.Model):
    annual_exam = models.ForeignKey(AnnualExam, on_delete=models.CASCADE, related_name='class_statistics')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='annual_exam_class_statistics')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='annual_exam_statistics')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='annual_exam_class_statistics_year', null=True)
    max_score = models.DecimalField(max_digits=4, decimal_places=2,null=True)
    min_score = models.DecimalField(max_digits=4, decimal_places=2,null=True)
    avg_score = models.DecimalField(max_digits=4, decimal_places=2,null=True)
    num_students = models.PositiveIntegerField(null=True)
    num_passed = models.PositiveIntegerField(null=True)
    percentage_passed = models.DecimalField(max_digits=5, decimal_places=2,null=True)

    class Meta:
        unique_together = ('annual_exam', 'class_obj', 'class_subject')

    def __str__(self):
        return f"{self.class_subject.subject.name} - {self.class_obj.name} - {self.annual_exam.name}"


class AnnualExamOverallStatistics(models.Model):
    annual_exam = models.ForeignKey(AnnualExam, on_delete=models.CASCADE, related_name='overall_statistics')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='annual_exam_overall_statistics')
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='annual_exam_overall_statistics_year', null=True)
    num_students = models.PositiveIntegerField(null=True)
    num_passes = models.PositiveIntegerField(null=True)
    class_average = models.DecimalField(max_digits=4, decimal_places=2,null=True)
    overall_percentage_pass = models.DecimalField(max_digits=5, decimal_places=2,null=True)

    class Meta:
        unique_together = ('annual_exam', 'class_obj')

    def __str__(self):
        return f"Overall Stats - {self.class_obj.name} - {self.annual_exam.name}"



class ExtraExamData(models.Model):
    RATING_CHOICES = [
        (5, 'Excellent'),
        (4, 'Very Good'),
        (3, 'Satisfactory'),
        (2, 'Unsatisfactory'),
        (1, 'Poor'),
    ]

    academic_year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='extra_exam_data')
    class_obj = models.ForeignKey('Class', on_delete=models.CASCADE, related_name='extra_exam_data')
    general_exam = models.ForeignKey('GeneralExam', on_delete=models.CASCADE, related_name='extra_exam_data')
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='extra_exam_data')
    absences = models.PositiveIntegerField(default=0, help_text="Number of absences during the exam period.")
    conduct = models.PositiveIntegerField(choices=RATING_CHOICES,help_text="Conduct rating: 1 = Poor, to 5 = Excellent")
    human_investment = models.PositiveIntegerField(choices=RATING_CHOICES,help_text="Human investment rating: 1 = Poor, to 5 = Excellent")
    fees_owed = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'),help_text="Amount of fees owed in CFA.")
    participation_in_extracurricular = models.BooleanField(default=False,help_text="Did the student participate in extracurricular activities?")
    remarks = models.TextField(blank=True, help_text="General remarks or observations by teachers.", default="General student remark")

    class Meta:
        unique_together = ('academic_year', 'class_obj', 'general_exam', 'student')
        verbose_name_plural = 'Extra Exam Data'

    def __str__(self):
        return f"Extra Data for {self.student.get_full_name()} in {self.class_obj.name} ({self.academic_year.year})"











