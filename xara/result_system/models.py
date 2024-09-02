from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum, Avg
from django.utils.text import Truncator
from decimal import Decimal, ROUND_HALF_UP


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
    max_students_per_class = models.PositiveIntegerField(default=1000)
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
    capacity = models.PositiveIntegerField(default=2000)

    class Meta:
        unique_together = ('school', 'name', 'academic_year')
        verbose_name_plural = 'Classes'

    def __str__(self):
        return f"{self.name} - {self.academic_year.year}"

    def get_current_student_count(self):
        return self.current_students.count()

    def is_full(self):
        return self.get_current_student_count() >= self.capacity

    def get_class_average(self, exam=None):
        results = Result.objects.filter(
            student__current_class=self,
            exam__academic_year=self.academic_year
        )
        if exam:
            results = results.filter(exam=exam)
        return results.aggregate(Avg('mark'))['mark__avg'] or 0

    def get_subject_averages(self, exam=None):
        results = Result.objects.filter(
            student__current_class=self,
            exam__academic_year=self.academic_year
        )
        if exam:
            results = results.filter(exam=exam)
        return results.values('class_subject__subject__name').annotate(average=Avg('mark'))

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

    def get_subject_average(self, class_obj, exam=None):
        results = Result.objects.filter(
            class_subject__subject=self,
            class_subject__class_obj=class_obj,
            exam__academic_year=class_obj.academic_year
        )
        if exam:
            results = results.filter(exam=exam)
        return results.aggregate(Avg('mark'))['mark__avg'] or 0

    def toggle_active(self):
        self.is_active = not self.is_active
        self.save()

    def get_classes(self):
        return self.classes.filter(class_obj__academic_year__is_current=True)


class ClassSubject(models.Model):
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='classes')
    credit = models.DecimalField(max_digits=3, decimal_places=1)
    max_students = models.PositiveIntegerField(default=2000, help_text="0 means no limit")

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
        return self.student_subjects.count()

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

    def get_exam_statistics(self, class_obj=None):
        results = self.results.all()
        if class_obj:
            results = results.filter(student__current_class=class_obj)
        
        return {
            'average': results.aggregate(Avg('mark'))['mark__avg'] or 0,
            'highest': results.aggregate(models.Max('mark'))['mark__max'] or 0,
            'lowest': results.aggregate(models.Min('mark'))['mark__min'] or 0,
            'pass_rate': (results.filter(mark__gte=self.school.settings.default_pass_mark).count() / results.count()) * 100 if results.count() > 0 else 0
        }

class GeneralExam(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='general_exams')
    name = models.CharField(max_length=100)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='general_exams')
    exams = models.ManyToManyField(Exam, related_name='general_exams')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    class Meta:
        unique_together = ('school', 'name', 'academic_year')

    def __str__(self):
        return f"{self.name} - {self.academic_year}"

class Result(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='results')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='results')
    mark = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    comments = models.TextField(blank=True)

    class Meta:
        unique_together = ('student', 'class_subject', 'exam')
        indexes = [
            models.Index(fields=['student', 'exam']),
            models.Index(fields=['class_subject', 'exam']),
        ]

    def __str__(self):
        return f"{self.student} - {self.class_subject.subject} - {self.exam}: {self.mark}"

    def clean(self):
        super().clean()
        grading_system = self.student.school.settings.grading_system
        for grade, range_info in grading_system.items():
            if range_info['min'] <= self.mark <= range_info['max']:
                return
        raise ValidationError("The mark does not fall within any defined grade range.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


    def calculate_grade(self):
        grading_system = self.student.school.settings.grading_system
        for grade, range_info in grading_system.items():
            if range_info['min'] <= self.mark <= range_info['max']:
                return grade
        raise ValidationError("The mark does not fall within any defined grade range.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Attendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    is_present = models.BooleanField(default=True)
    reason = models.TextField(blank=True)

    class Meta:
        unique_together = ('student', 'class_subject', 'date')
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['class_subject', 'date']),
        ]

    def __str__(self):
        return f"{self.student} - {self.class_subject} - {self.date}"

class ReportCard(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='report_cards')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    generated_at = models.DateTimeField(auto_now_add=True)
    total_average = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    class_rank = models.PositiveIntegerField(null=True, blank=True)
    comments = models.TextField(blank=True)

    class Meta:
        unique_together = ('student', 'academic_year')

    def __str__(self):
        return f"Report Card - {self.student} - {self.academic_year}"

    def generate(self):
        results = Result.objects.filter(
            student=self.student,
            exam__academic_year=self.academic_year
        ).select_related('class_subject', 'exam')

        subject_averages = {}
        for result in results:
            subject = result.class_subject.subject
            if subject not in subject_averages:
                subject_averages[subject] = {'total': 0, 'count': 0}
            subject_averages[subject]['total'] += result.mark
            subject_averages[subject]['count'] += 1

        total_average = 0
        total_credits = 0
        for subject, data in subject_averages.items():
            average = data['total'] / data['count']
            credit = result.class_subject.credit
            total_average += average * credit
            total_credits += credit

        self.total_average = total_average / total_credits if total_credits > 0 else 0
        self.save()




    def calculate_class_rank(self):
        class_averages = ReportCard.objects.filter(
            academic_year=self.academic_year,
            student__current_class=self.student.current_class
        ).values_list('total_average', flat=True)

        # Round averages to a consistent precision
        rounded_total_average = self.total_average.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        rounded_class_averages = [avg.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for avg in class_averages]

        # Tolerance for floating-point comparison
        tolerance = Decimal('0.01')

        # Find the rank by comparing within a tolerance
        for index, avg in enumerate(sorted(rounded_class_averages, reverse=True)):
            if abs(avg - rounded_total_average) <= tolerance:
                self.class_rank = index + 1
                break
        else:
            # Handle the unlikely case where no match is found within the tolerance
            self.class_rank = len(rounded_class_averages) + 1

        self.save()


class AttendanceReport(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_reports')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    total_days = models.PositiveIntegerField(default=0)
    days_present = models.PositiveIntegerField(default=0)
    days_absent = models.PositiveIntegerField(default=0)
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        unique_together = ('student', 'academic_year')

    def __str__(self):
        return f"Attendance Report - {self.student} - {self.academic_year}"

    def generate(self):
        attendances = Attendance.objects.filter(
            student=self.student,
            date__range=(self.academic_year.start_date, self.academic_year.end_date)
        )
        self.total_days = attendances.count()
        self.days_present = attendances.filter(is_present=True).count()
        self.days_absent = self.total_days - self.days_present
        self.attendance_percentage = (self.days_present / self.total_days * 100) if self.total_days > 0 else 0
        self.save()