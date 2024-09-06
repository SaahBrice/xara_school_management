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
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grade_sheets')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='grade_sheets')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='grade_sheets')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='grade_sheets')
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

    def calculate_totals_and_average(self, prevent_recursive_save=False):
        try:
            with transaction.atomic():
                subject_grades = self.subject_grades.all().select_related('class_subject')
                
                aggregates = subject_grades.aggregate(
                    total_score=Sum('score'),
                    credits_attempted=Sum('class_subject__credit'),
                    credits_obtained=Sum(Case(
                        When(score__gte=10, then=F('class_subject__credit')),
                        default=0,
                        output_field=DecimalField()
                    ))
                )

                self.total_score = aggregates['total_score'] or 0
                self.credits_attempted = aggregates['credits_attempted'] or 0
                self.credits_obtained = aggregates['credits_obtained'] or 0
                
                if self.credits_attempted > 0:
                    self.average = self.total_score / self.credits_attempted
                else:
                    self.average = Decimal(0)

                self.remark = 'PASSED' if float(self.average) >= 10 else 'FAILED'

                # Prevent recursion using flag
                if not prevent_recursive_save:
                    self.save(prevent_recursive_save=True)

                # Update statistics
                ClassStatistics.update_statistics(self.exam, self.class_obj, self.academic_year)
                OverallStatistics.update_statistics(self.exam, self.class_obj, self.academic_year)
        except Exception as e:
            raise GradeCalculationError(f"Error calculating totals and average: {str(e)}")

    def calculate_rank(self, prevent_recursive_save=False):
        try:
            with transaction.atomic():
                grade_sheets = GradeSheet.objects.filter(exam=self.exam, class_obj=self.class_obj)
                sorted_averages = grade_sheets.order_by('-average').values_list('id', 'average')
                
                rank_mapping = {id: rank + 1 for rank, (id, _) in enumerate(sorted_averages)}
                self.rank = rank_mapping[self.id]

                if not prevent_recursive_save:
                    self.save(prevent_recursive_save=True)
        except Exception as e:
            raise RankCalculationError(f"Error calculating rank: {str(e)}")

    @classmethod
    def bulk_update_ranks(cls, exam, class_obj):
        """
        Bulk update ranks for all grade sheets in a given exam and class.
        """
        try:
            with transaction.atomic():
                grade_sheets = cls.objects.filter(exam=exam, class_obj=class_obj)
                sorted_grade_sheets = sorted(grade_sheets, key=lambda gs: gs.average, reverse=True)
                
                for rank, grade_sheet in enumerate(sorted_grade_sheets, start=1):
                    grade_sheet.rank = rank
                
                cls.objects.bulk_update(sorted_grade_sheets, ['rank'])
        except Exception as e:
            raise GradeCalculationError(f"Error bulk updating ranks: {str(e)}")


@receiver(post_save, sender=GradeSheet)
def update_grade_sheet(sender, instance, created, **kwargs):
    if not created and not kwargs.get('prevent_recursive_save', False):
        instance.calculate_totals_and_average(prevent_recursive_save=True)
        GradeSheet.bulk_update_ranks(instance.exam, instance.class_obj)




class SubjectGrade(models.Model):
    grade_sheet = models.ForeignKey(GradeSheet, on_delete=models.CASCADE, related_name='subject_grades')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='subject_grades')
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

    def save(self, *args, **kwargs):
        """
        Save the subject grade, update related fields, and recalculate statistics.
        """
        # Flag to prevent recursion
        if kwargs.pop('prevent_recursive_save', False):
            super().save(*args, **kwargs)
            return
        
        with transaction.atomic():
            if self.score is not None:
                self.exam_taken = True
                self.set_observation()
            
            super().save(*args, **kwargs)
            
            self.calculate_rank(save_rank=False)
            self.grade_sheet.calculate_totals_and_average(prevent_recursive_save=True)

    def set_observation(self):
        """
        Set the observation based on the grading system and the current score.
        """
        grading_system = self.grade_sheet.student.school.settings.grading_system
        for grade, range_info in grading_system.items():
            if range_info['min'] <= self.score <= range_info['max']:
                self.observation = range_info['description']
                break

    def calculate_rank(self, save_rank = True ):
        """
        Calculate and update the rank of this subject grade within the class.
        """
        with transaction.atomic():
            subject_grades = SubjectGrade.objects.filter(
                grade_sheet__exam=self.grade_sheet.exam,
                grade_sheet__class_obj=self.grade_sheet.class_obj,
                class_subject=self.class_subject
            ).order_by('-score')
            
            self.rank = list(subject_grades.values_list('score', flat=True)).index(self.score) + 1
            if save_rank:
                self.save(update_fields=['rank'])

    @classmethod
    def bulk_create_or_update(cls, grades_data):
        """
        Bulk create or update subject grades.
        
        :param grades_data: List of dictionaries containing grade data
        """
        bulk_mgr = BulkCreateManager(chunk_size=100)
        for data in grades_data:
            try:
                grade, created = cls.objects.get_or_create(
                    grade_sheet=data['grade_sheet'],
                    class_subject=data['class_subject'],
                    defaults={'score': data['score']}
                )
                if not created:
                    grade.score = data['score']
                bulk_mgr.add(grade, update=not created)
            except Exception as e:
                raise GradeCreationError(f"Error creating/updating grade: {str(e)}")
        bulk_mgr.done()
        
    @classmethod
    def bulk_update_ranks(cls, exam, class_obj, class_subject):
        with transaction.atomic():
            subject_grades = cls.objects.filter(
                grade_sheet__exam=exam,
                grade_sheet__class_obj=class_obj,
                class_subject=class_subject
            ).select_related('grade_sheet')
            
            sorted_grades = sorted(subject_grades, key=lambda sg: sg.score, reverse=True)
            
            for rank, grade in enumerate(sorted_grades, start=1):
                grade.rank = rank
            
            cls.objects.bulk_update(sorted_grades, ['rank'])





class ClassStatistics(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='class_statistics')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='class_statistics')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='class_statistics')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='class_statistics')
    max_score = models.DecimalField(max_digits=4, decimal_places=2)
    min_score = models.DecimalField(max_digits=4, decimal_places=2)
    avg_score = models.DecimalField(max_digits=4, decimal_places=2)
    num_sat = models.PositiveIntegerField()
    num_passed = models.PositiveIntegerField()
    percentage_passed = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('exam', 'class_obj', 'class_subject', 'academic_year')

    def __str__(self):
        return f"{self.class_subject.subject.name} - {self.class_obj.name} - {self.exam.name} - {self.academic_year}"

    @classmethod
    def update_statistics(cls, exam, class_obj, academic_year):
        with transaction.atomic():
            for class_subject in class_obj.subjects.all():
                # Get subject grades for the specific class and exam
                subject_grades = SubjectGrade.objects.filter(
                    grade_sheet__exam=exam,
                    grade_sheet__class_obj=class_obj,
                    class_subject=class_subject
                )

                # Only process statistics if there are subject grades (students took the exam)
                if subject_grades.exists():
                    # Aggregate the scores
                    stats = subject_grades.aggregate(
                        max_score=Max('score'),
                        min_score=Min('score'),
                        avg_score=Avg('score'),
                        num_sat=Count('id'),
                        num_passed=Count('id', filter=Q(score__gte=10))
                    )

                    # Calculate the pass percentage
                    if stats['num_sat'] > 0:
                        stats['percentage_passed'] = (stats['num_passed'] / stats['num_sat']) * 100
                    else:
                        stats['percentage_passed'] = 0

                    # Ensure that max_score, min_score, and avg_score are not None
                    if stats['max_score'] is None or stats['min_score'] is None or stats['avg_score'] is None:
                        continue  # Skip updating this subject if no meaningful data exists

                    # Update or create the statistics for this class subject
                    cls.objects.update_or_create(
                        exam=exam,
                        class_obj=class_obj,
                        class_subject=class_subject,
                        academic_year=academic_year,
                        defaults={
                            'max_score': stats['max_score'],
                            'min_score': stats['min_score'],
                            'avg_score': stats['avg_score'],
                            'num_sat': stats['num_sat'],
                            'num_passed': stats['num_passed'],
                            'percentage_passed': stats['percentage_passed'],
                        }
                    )

class OverallStatistics(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='overall_statistics')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='overall_statistics')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='overall_statistics')
    num_students = models.PositiveIntegerField()
    num_passes = models.PositiveIntegerField()
    class_average = models.DecimalField(max_digits=4, decimal_places=2)
    overall_percentage_pass = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('exam', 'class_obj', 'academic_year')

    def __str__(self):
        return f"Overall Stats - {self.class_obj.name} - {self.exam.name} - {self.academic_year}"

    @classmethod
    def update_statistics(cls, exam, class_obj, academic_year):
        with transaction.atomic():
            grade_sheets = GradeSheet.objects.filter(exam=exam, class_obj=class_obj)
            stats = grade_sheets.aggregate(
                num_students=Count('id'),
                num_passes=Count('id', filter=Q(average__gte=10)),
                class_average=Avg('average')
            )
            stats['overall_percentage_pass'] = (stats['num_passes'] / stats['num_students'] * 100) if stats['num_students'] > 0 else 0
            
            cls.objects.update_or_create(
                exam=exam,
                class_obj=class_obj,
                academic_year=academic_year,
                defaults=stats
            )








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

    def calculate_student_average(self, student):
        grade_sheets = GradeSheet.objects.filter(
            student=student,
            exam__in=self.exams.all(),
            academic_year=self.academic_year
        ).annotate(
            weighted_average=ExpressionWrapper(
                F('average') * F('exam__generalexamweight__weight'),
                output_field=DecimalField()
            )
        )
        
        total_weight = self.exams.aggregate(
            total_weight=Sum('generalexamweight__weight')
        )['total_weight'] or 1

        student_average = grade_sheets.aggregate(
            avg=Sum('weighted_average') / total_weight
        )['avg'] or 0

        return student_average

    def calculate_subject_averages(self):
        subject_grades = SubjectGrade.objects.filter(
            grade_sheet__exam__in=self.exams.all(),
            grade_sheet__academic_year=self.academic_year
        ).annotate(
            weighted_score=ExpressionWrapper(
                F('score') * F('grade_sheet__exam__generalexamweight__weight'),
                output_field=DecimalField()
            )
        )

        total_weight = self.exams.aggregate(
            total_weight=Sum('generalexamweight__weight')
        )['total_weight'] or 1

        subject_averages = subject_grades.values('class_subject__subject__name').annotate(
            average=Sum('weighted_score') / total_weight,
            max_score=Max('score'),
            min_score=Min('score'),
            num_students=Count('grade_sheet__student', distinct=True)
        )

        return subject_averages

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
    total_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    average = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    rank = models.PositiveIntegerField(blank=True, null=True)
    remark = models.CharField(max_length=20, blank=True)

    class Meta:
        unique_together = ('student', 'general_exam', 'class_obj', 'academic_year')

    def __str__(self):
        return f"{self.student.get_full_name()} - {self.general_exam.name} - {self.class_obj.name} - {self.academic_year}"

    def calculate_total_and_average(self, prevent_recursive_save=False):
        """
        Calculate and update the total score, credits attempted, credits obtained,
        average, and remark for this grade sheet.
        """
        try:
            with transaction.atomic():
                subject_grades = self.subject_grades.all().select_related('class_subject')

                aggregates = subject_grades.aggregate(
                    total_score=Sum('calculated_score'),
                    credits_attempted=Sum('class_subject__credit'),
                    credits_obtained=Sum(Case(
                        When(calculated_score__gte=10, then=F('class_subject__credit')),
                        default=0,
                        output_field=DecimalField()
                    ))
                )

                self.total_score = aggregates['total_score'] or 0
                self.credits_attempted = aggregates['credits_attempted'] or 0
                self.credits_obtained = aggregates['credits_obtained'] or 0

                if self.credits_attempted > 0:
                    self.average = self.total_score / self.credits_attempted
                else:
                    self.average = Decimal(0.00)

                self.remark = 'PASSED' if float(self.average) >= 10 else 'FAILED'

                # Avoid recursive save calls by using a flag
                if not prevent_recursive_save:
                    self.save(prevent_recursive_save=True)

                # Update class statistics (ensure this doesn't cause recursion)
                GeneralExamClassStatistics.update_statistics(self.general_exam, self.class_obj)
                GeneralExamOverallStatistics.update_statistics(self.general_exam, self.class_obj)
        except Exception as e:
            raise GradeCalculationError(f"Error calculating totals and average: {str(e)}")

    def calculate_rank(self, prevent_recursive_save=False):
        """
        Calculate and update the rank for the student within the class.
        """
        try:
            with transaction.atomic():
                # Logic for calculating rank
                ranks = GeneralExamGradeSheet.objects.filter(
                    exam=self.exam,
                    class_obj=self.class_obj,
                    academic_year=self.academic_year
                ).order_by('-total_score')

                rank_map = {gs.id: rank + 1 for rank, gs in enumerate(ranks)}
                self.rank = rank_map[self.id]

                if not prevent_recursive_save:
                    self.save(prevent_recursive_save=True)
        except Exception as e:
            raise RankCalculationError(f"Error calculating rank: {str(e)}")

@receiver(post_save, sender=GeneralExamGradeSheet)
def update_general_exam_grade_sheet(sender, instance, created, **kwargs):
    """
    Post-save signal to update the grade sheet's totals, averages, and rank after saving.
    """
    if not created and not kwargs.get('prevent_recursive_save', False):
        instance.calculate_total_and_average(prevent_recursive_save=True)
        instance.calculate_rank(prevent_recursive_save=True)




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

    def save(self, *args, **kwargs):
        with transaction.atomic():
            prevent_recursive_save = kwargs.pop('prevent_recursive_save', False)
            if not prevent_recursive_save:
                # Calculate score only if recursion is not being prevented
                self.calculate_score()
            self.set_observation()
            super().save(*args, **kwargs)
            if not kwargs.get('prevent_recursive_save', False):
                self.calculate_rank(prevent_recursive_save=True)
                self.grade_sheet.calculate_total_and_average(prevent_recursive_save=True)

    def calculate_score(self):
        subject_grades = SubjectGrade.objects.filter(
            grade_sheet__student=self.grade_sheet.student,
            grade_sheet__exam__in=self.grade_sheet.general_exam.exams.all(),
            class_subject=self.class_subject
        ).annotate(
            weighted_score=ExpressionWrapper(
                F('score') * F('grade_sheet__exam__generalexamweight__weight'),
                output_field=DecimalField()
            )
        )

        total_weight = self.grade_sheet.general_exam.exams.aggregate(
            total_weight=Sum('generalexamweight__weight')
        )['total_weight'] or 1

        self.calculated_score = subject_grades.aggregate(
            avg=Sum('weighted_score') / total_weight
        )['avg'] or 0

        self.set_observation()

    def set_observation(self):
        grading_system = self.grade_sheet.student.school.settings.grading_system
        for grade, range_info in grading_system.items():
            if range_info['min'] <= self.calculated_score <= range_info['max']:
                self.observation = range_info['description']
                break

    def calculate_rank(self, prevent_recursive_save=True):
        with transaction.atomic():
            subject_grades = GeneralExamSubjectGrade.objects.filter(
                grade_sheet__general_exam=self.grade_sheet.general_exam,
                grade_sheet__class_obj=self.grade_sheet.class_obj,
                class_subject=self.class_subject
            ).order_by('-calculated_score')
            
            rank_mapping = {grade.id: rank + 1 for rank, grade in enumerate(subject_grades)}
            self.rank = rank_mapping[self.id]
            
            if not prevent_recursive_save:
                self.save(prevent_recursive_save=True)



class GeneralExamClassStatistics(models.Model):
    general_exam = models.ForeignKey(GeneralExam, on_delete=models.CASCADE, related_name='class_statistics')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='general_exam_class_statistics')
    class_subject = models.ForeignKey(ClassSubject, on_delete=models.CASCADE, related_name='general_exam_statistics')
    max_score = models.DecimalField(max_digits=4, decimal_places=2)
    min_score = models.DecimalField(max_digits=4, decimal_places=2)
    avg_score = models.DecimalField(max_digits=4, decimal_places=2)
    num_students = models.PositiveIntegerField()
    num_passed = models.PositiveIntegerField()
    percentage_passed = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('general_exam', 'class_obj', 'class_subject')

    def __str__(self):
        return f"{self.class_subject.subject.name} - {self.class_obj.name} - {self.general_exam.name}"

    @classmethod
    def update_statistics(cls, general_exam, class_obj):
        with transaction.atomic():
            for class_subject in class_obj.subjects.all():
                subject_grades = GeneralExamSubjectGrade.objects.filter(
                    grade_sheet__general_exam=general_exam,
                    grade_sheet__class_obj=class_obj,
                    class_subject=class_subject
                )
                stats = subject_grades.aggregate(
                    max_score=Max('calculated_score'),
                    min_score=Min('calculated_score'),
                    avg_score=Avg('calculated_score'),
                    num_students=Count('id'),
                    num_passed=Count('id', filter=Q(calculated_score__gte=10))
                )
                stats['percentage_passed'] = (stats['num_passed'] / stats['num_students']) * 100 if stats['num_students'] > 0 else 0
                                # Ensure all required fields have default values
                stats['max_score'] = stats['max_score'] or Decimal('0.00')
                stats['min_score'] = stats['min_score'] or Decimal('0.00')
                stats['avg_score'] = stats['avg_score'] or Decimal('0.00')
                stats['num_students'] = stats['num_students'] or 0
                stats['num_passed'] = stats['num_passed'] or 0
                stats['percentage_passed'] = (stats['num_passed'] / stats['num_students']) * 100 if stats['num_students'] > 0 else Decimal('0.00')

                cls.objects.update_or_create(
                    general_exam=general_exam,
                    class_obj=class_obj,
                    class_subject=class_subject,
                    defaults=stats
                )

class GeneralExamOverallStatistics(models.Model):
    general_exam = models.ForeignKey(GeneralExam, on_delete=models.CASCADE, related_name='overall_statistics')
    class_obj = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='general_exam_overall_statistics')
    num_students = models.PositiveIntegerField()
    num_passes = models.PositiveIntegerField()
    class_average = models.DecimalField(max_digits=4, decimal_places=2)
    overall_percentage_pass = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('general_exam', 'class_obj')

    def __str__(self):
        return f"Overall Stats - {self.class_obj.name} - {self.general_exam.name}"

    @classmethod
    def update_statistics(cls, general_exam, class_obj):
        with transaction.atomic():
            grade_sheets = GeneralExamGradeSheet.objects.filter(
                general_exam=general_exam,
                class_obj=class_obj
            )
            stats = grade_sheets.aggregate(
                num_students=Count('id'),
                num_passes=Count('id', filter=Q(average__gte=10)),
                class_average=Avg('average')
            )
            stats['overall_percentage_pass'] = (stats['num_passes'] / stats['num_students']) * 100 if stats['num_students'] > 0 else 0

            cls.objects.update_or_create(
                general_exam=general_exam,
                class_obj=class_obj,
                defaults=stats
            )

def get_cached_class_statistics(exam, class_obj, class_subject):
    cache_key = f'class_stats_{exam.id}_{class_obj.id}_{class_subject.id}'
    stats = cache.get(cache_key)
    if not stats:
        stats = ClassStatistics.objects.filter(
            exam=exam,
            class_obj=class_obj,
            class_subject=class_subject
        ).first()
        if stats:
            cache.set(cache_key, stats, timeout=3600)  # Cache for 1 hour
    return stats

def get_cached_overall_statistics(exam, class_obj):
    cache_key = f'overall_stats_{exam.id}_{class_obj.id}'
    stats = cache.get(cache_key)
    if not stats:
        stats = OverallStatistics.objects.filter(
            exam=exam,
            class_obj=class_obj
        ).first()
        if stats:
            cache.set(cache_key, stats, timeout=3600)  # Cache for 1 hour
    return stats

# Add signals to invalidate cache when statistics are updated

@receiver(post_save, sender=ClassStatistics)
def invalidate_class_statistics_cache(sender, instance, **kwargs):
    cache_key = f'class_stats_{instance.exam.id}_{instance.class_obj.id}_{instance.class_subject.id}'
    cache.delete(cache_key)

@receiver(post_save, sender=OverallStatistics)
def invalidate_overall_statistics_cache(sender, instance, **kwargs):
    cache_key = f'overall_stats_{instance.exam.id}_{instance.class_obj.id}'
    cache.delete(cache_key)

# Optimize bulk operations for performance

class BulkCreateManager(object):
    def __init__(self, chunk_size=100):
        self._create_queue = []
        self._update_queue = []
        self._chunk_size = chunk_size

    def add(self, obj, update=False):
        if update:
            self._update_queue.append(obj)
        else:
            self._create_queue.append(obj)

        if len(self._create_queue) >= self._chunk_size:
            self.done()

    def done(self):
        if self._create_queue:
            self.model_class.objects.bulk_create(self._create_queue)
            self._create_queue = []
        if self._update_queue:
            self.model_class.objects.bulk_update(self._update_queue, self.update_fields)
            self._update_queue = []







