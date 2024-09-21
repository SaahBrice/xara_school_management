from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ExtraExamData, School, SystemSettings, AcademicYear, Class, Subject, ClassSubject,
    User, Teacher, TeacherSubject, Student, StudentDocument, StudentSubject,
    Exam, GradeSheet, SubjectGrade, ClassStatistics, OverallStatistics,
    GeneralExam, GeneralExamWeight, GeneralExamGradeSheet, GeneralExamSubjectGrade,
    GeneralExamClassStatistics, GeneralExamOverallStatistics
)
from django.contrib.auth.admin import UserAdmin

admin.site.site_header = "School Management System"
admin.site.site_title = "School Management Admin Portal"
admin.site.index_title = "Welcome to School Management Portal"

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'phone', 'email', 'website')
    search_fields = ('name', 'code')

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('school', 'school_initials', 'academic_year_format', 'max_students_per_class')

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('school', 'year', 'start_date', 'end_date', 'is_current')
    list_filter = ('school', 'is_current')

@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'academic_year', 'capacity', 'get_class_master')
    list_filter = ('school', 'academic_year')
    search_fields = ('name',)

    def get_class_master(self, obj):
        return obj.get_class_master_name()
    get_class_master.short_description = 'Class Master'

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'school', 'default_credit', 'subject_type', 'is_active')
    list_filter = ('school', 'subject_type', 'is_active')
    search_fields = ('name', 'code')

@admin.register(ClassSubject)
class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ('class_obj', 'subject', 'credit', 'max_students', 'is_active')
    list_filter = ('class_obj__school', 'is_active')

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
    list_display = ('user', 'get_school', 'date_joined')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')

    def get_school(self, obj):
        return obj.user.school
    get_school.short_description = 'School'

@admin.register(TeacherSubject)
class TeacherSubjectAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'subject', 'class_obj', 'assigned_date')
    list_filter = ('class_obj__school', 'subject')

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('matricula_code', 'get_full_name', 'current_class', 'school', 'is_active')
    list_filter = ('school', 'current_class', 'is_active')
    search_fields = ('first_name', 'last_name', 'matricula_code')
    fieldsets = (
        ('Personal Information', {
            'fields': ('school', 'first_name', 'last_name', 'matricula_code', 'date_of_birth', 'gender', 'picture')
        }),
        ('Contact Information', {
            'fields': ('address', 'email', 'phone')
        }),
        ('Academic Information', {
            'fields': ('current_class', 'date_enrolled', 'is_active')
        }),
        ('Parent Information', {
            'fields': ('parent_name', 'parent_contact', 'parent_email', 'parent_address')
        }),
        ('Results Access', {
            'fields': ('results_access_payed', 'results_access_date_payed', 'results_access_phone_number_payed')
        }),
    )

@admin.register(StudentDocument)
class StudentDocumentAdmin(admin.ModelAdmin):
    list_display = ('student', 'document_type', 'uploaded_at')
    list_filter = ('document_type', 'uploaded_at')

@admin.register(StudentSubject)
class StudentSubjectAdmin(admin.ModelAdmin):
    list_display = ('student', 'class_subject', 'academic_year', 'is_active')
    list_filter = ('academic_year', 'is_active')

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'academic_year', 'start_date', 'end_date', 'is_active')
    list_filter = ('school', 'academic_year', 'is_active')
    search_fields = ('name',)

class SubjectGradeInline(admin.TabularInline):
    model = SubjectGrade
    extra = 1

@admin.register(GradeSheet)
class GradeSheetAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'class_obj', 'total_score', 'average', 'remark', 'rank')
    list_filter = ('exam', 'class_obj', 'remark')
    search_fields = ('student__first_name', 'student__last_name', 'student__matricula_code')
    inlines = [SubjectGradeInline]

@admin.register(ClassStatistics)
class ClassStatisticsAdmin(admin.ModelAdmin):
    list_display = ('exam', 'class_obj', 'class_subject', 'avg_score', 'num_sat', 'num_passed', 'percentage_passed')
    list_filter = ('exam', 'class_obj')

@admin.register(OverallStatistics)
class OverallStatisticsAdmin(admin.ModelAdmin):
    list_display = ('exam', 'class_obj', 'num_students', 'num_passes', 'class_average', 'overall_percentage_pass')
    list_filter = ('exam', 'class_obj')

@admin.register(GeneralExam)
class GeneralExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'school', 'academic_year', 'start_date', 'end_date')
    list_filter = ('school', 'academic_year')


@admin.register(GeneralExamWeight)
class GeneralExamWeightAdmin(admin.ModelAdmin):
    list_display = ('general_exam', 'exam', 'weight')

@admin.register(GeneralExamGradeSheet)
class GeneralExamGradeSheetAdmin(admin.ModelAdmin):
    list_display = ('student', 'general_exam', 'class_obj', 'total_score', 'average', 'remark', 'rank')
    list_filter = ('general_exam', 'class_obj', 'remark')
    search_fields = ('student__first_name', 'student__last_name', 'student__matricula_code')

@admin.register(GeneralExamClassStatistics)
class GeneralExamClassStatisticsAdmin(admin.ModelAdmin):
    list_display = ('general_exam', 'class_obj', 'class_subject', 'avg_score', 'num_students', 'num_passed', 'percentage_passed')
    list_filter = ('general_exam', 'class_obj')

@admin.register(GeneralExamOverallStatistics)
class GeneralExamOverallStatisticsAdmin(admin.ModelAdmin):
    list_display = ('general_exam', 'class_obj', 'num_students', 'num_passes', 'class_average', 'overall_percentage_pass')
    list_filter = ('general_exam', 'class_obj')


@admin.register(ExtraExamData)
class ExtraExamDataAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_year', 'class_obj', 'general_exam', 'absences', 'conduct', 'human_investment', 'fees_owed', 'participation_in_extracurricular')
    list_filter = ('academic_year', 'class_obj', 'general_exam', 'conduct', 'human_investment')
    search_fields = ('student__first_name', 'student__last_name', 'student__matricula_code')

    fieldsets = (
        ('Student and Exam Information', {
            'fields': ('academic_year', 'class_obj', 'general_exam', 'student')
        }),
        ('Performance and Conduct', {
            'fields': ('absences', 'conduct', 'human_investment', 'fees_owed', 'participation_in_extracurricular')
        }),
        ('Remarks', {
            'fields': ('remarks',)
        }),
    )

    def get_student_name(self, obj):
        return obj.student.get_full_name()
    get_student_name.short_description = 'Student Name'

