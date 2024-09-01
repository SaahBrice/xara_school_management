from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    School, SystemSettings, AcademicYear, Class, Subject, ClassSubject,
    User, Teacher, TeacherSubject, Student, StudentDocument, StudentSubject,
    Exam, GeneralExam, Result, Attendance, ReportCard, AttendanceReport
)

admin.site.site_header = "Xara School Management System"
admin.site.site_title = "Xara SMS Admin"
admin.site.index_title = "Welcome to Xara School Management System"

class SystemSettingsInline(admin.StackedInline):
    model = SystemSettings
    can_delete = False

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'email', 'phone')
    search_fields = ('name', 'code', 'email')
    inlines = [SystemSettingsInline]

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('school', 'year', 'start_date', 'end_date', 'is_current')
    list_filter = ('school', 'is_current')
    search_fields = ('year', 'school__name')
    date_hierarchy = 'start_date'

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'academic_year', 'capacity')
    list_filter = ('school', 'academic_year')
    search_fields = ('name', 'school__name')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'default_credit', 'subject_type')
    list_filter = ('school', 'subject_type')
    search_fields = ('name', 'code', 'school__name')

@admin.register(ClassSubject)
class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ('class_obj', 'subject', 'credit', 'max_students')
    list_filter = ('class_obj__school', 'class_obj__academic_year')
    search_fields = ('class_obj__name', 'subject__name')

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'school')
    list_filter = ('user_type', 'school')
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'school', 'phone')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'school', 'phone')}),
    )

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'qualifications', 'date_joined')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    date_hierarchy = 'date_joined'

@admin.register(TeacherSubject)
class TeacherSubjectAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'subject', 'class_obj', 'assigned_date')
    list_filter = ('class_obj__school', 'class_obj__academic_year')
    search_fields = ('teacher__user__username', 'subject__name', 'class_obj__name')
    date_hierarchy = 'assigned_date'

class StudentDocumentInline(admin.TabularInline):
    model = StudentDocument
    extra = 1

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('matricula_code', 'first_name', 'last_name', 'current_class', 'date_enrolled')
    list_filter = ('school', 'current_class', 'date_enrolled')
    search_fields = ('matricula_code', 'first_name', 'last_name', 'email')
    inlines = [StudentDocumentInline]
    date_hierarchy = 'date_enrolled'

@admin.register(StudentSubject)
class StudentSubjectAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_subject', 'academic_year', 'enrollment_date', 'is_active')
    list_filter = ('academic_year', 'is_active')
    search_fields = ('student__matricula_code', 'student__first_name', 'student__last_name', 'class_subject__subject__name')
    date_hierarchy = 'enrollment_date'

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'academic_year', 'start_date', 'end_date', 'is_active', 'max_score')
    list_filter = ('school', 'academic_year', 'is_active')
    search_fields = ('name', 'school__name')
    date_hierarchy = 'start_date'

@admin.register(GeneralExam)
class GeneralExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'academic_year', 'start_date', 'end_date')
    list_filter = ('school', 'academic_year')
    search_fields = ('name', 'school__name')
    filter_horizontal = ('exams',)
    date_hierarchy = 'start_date'

@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_subject', 'exam', 'mark', 'created_by', 'created_at')
    list_filter = ('exam__school', 'exam__academic_year', 'class_subject__subject')
    search_fields = ('student__matricula_code', 'student__first_name', 'student__last_name', 'class_subject__subject__name')
    date_hierarchy = 'created_at'

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_subject', 'date', 'is_present')
    list_filter = ('is_present', 'class_subject__class_obj__school', 'class_subject__class_obj__academic_year')
    search_fields = ('student__matricula_code', 'student__first_name', 'student__last_name', 'class_subject__subject__name')
    date_hierarchy = 'date'

@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_year', 'total_average', 'class_rank', 'generated_at')
    list_filter = ('academic_year', 'student__current_class')
    search_fields = ('student__matricula_code', 'student__first_name', 'student__last_name')
    date_hierarchy = 'generated_at'

@admin.register(AttendanceReport)
class AttendanceReportAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_year', 'total_days', 'days_present', 'days_absent', 'attendance_percentage')
    list_filter = ('academic_year', 'student__current_class')
    search_fields = ('student__matricula_code', 'student__first_name', 'student__last_name')

# Optionally, you can customize the admin site further
# admin.site.site_header = "Xara School Management System"
# admin.site.site_title = "Xara SMS Admin"
# admin.site.index_title = "Welcome to Xara School Management System"