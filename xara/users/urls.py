from django.urls import path
from .views import (
    AcademicYearCreateView, AcademicYearDeleteView, AcademicYearListView, AcademicYearUpdateView, AddTeacherView, AssignSubjectView, ClassCreateView, ClassDeleteView, ClassListView, ClassUpdateView, CustomLoginView, CustomLogoutView, DashboardView, DeleteTeacherView, EditTeacherView, ExamCreateView, ExamDeleteView, ExamListView, ExamUpdateView, GeneralExamCreateView, GeneralExamDeleteView, GeneralExamListView, GeneralExamUpdateView,
    GenericDashboardView, ManageResultsView, ManageStudentSubjectsView, SetCurrentAcademicYearView, StudentDeleteView, SubjectCreateView, SubjectDeleteView, SubjectListView, SubjectUpdateView, SystemSettingsView, TeacherDashboardView, SecretaryDashboardView, TeacherDetailView,
    TeacherListView, ToggleStudentActiveView, ToggleSubjectActiveView, ToggleTeacherActiveView, StudentCreateView, StudentDetailView, StudentUpdateView, StudentListView, get_classes, get_exams, get_results, save_grade,
)

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),

    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('generic-dashboard/', GenericDashboardView.as_view(), name='generic_dashboard'),
    path('teacher-dashboard/', TeacherDashboardView.as_view(), name='teacher_dashboard'),
    path('secretary-dashboard/', SecretaryDashboardView.as_view(), name='secretary_dashboard'),

    path('teachers/', TeacherListView.as_view(), name='teacher_list'),
    path('teachers/add/', AddTeacherView.as_view(), name='add_teacher'),
    path('teachers/edit/<int:pk>/', EditTeacherView.as_view(), name='edit_teacher'),
    path('teachers/delete/<int:pk>/', DeleteTeacherView.as_view(), name='delete_teacher'),
    path('teachers/view/<int:pk>/', TeacherDetailView.as_view(), name='view_teacher'),
    path('teachers/toggle-active/<int:pk>/', ToggleTeacherActiveView.as_view(), name='toggle_teacher_active'),

    path('classes/', ClassListView.as_view(), name='class_list'),
    path('classes/add/', ClassCreateView.as_view(), name='class_add'),
    path('classes/<int:pk>/edit/', ClassUpdateView.as_view(), name='class_edit'),
    path('classes/<int:pk>/delete/', ClassDeleteView.as_view(), name='class_delete'),

    path('students/', StudentListView.as_view(), name='student_list'),
    path('students/add/', StudentCreateView.as_view(), name='student_add'),
    path('students/<int:pk>/', StudentDetailView.as_view(), name='student_detail'),
    path('students/<int:pk>/edit/', StudentUpdateView.as_view(), name='student_edit'),
    path('students/<int:pk>/delete/', StudentDeleteView.as_view(), name='student_delete'),
    path('students/<int:pk>/manage-subjects/', ManageStudentSubjectsView.as_view(), name='manage_student_subjects'),
    path('students/<int:pk>/toggle-active/', ToggleStudentActiveView.as_view(), name='toggle_student_active'),

    path('academic-years/', AcademicYearListView.as_view(), name='academic_year_list'),
    path('academic-years/add/', AcademicYearCreateView.as_view(), name='academic_year_add'),
    path('academic-years/<int:pk>/edit/', AcademicYearUpdateView.as_view(), name='academic_year_edit'),
    path('academic-years/<int:pk>/delete/', AcademicYearDeleteView.as_view(), name='academic_year_delete'),
    path('academic-years/<int:pk>/set-current/', SetCurrentAcademicYearView.as_view(), name='set_current_academic_year'),


    path('subjects/', SubjectListView.as_view(), name='subject_list'),
    path('subjects/add/', SubjectCreateView.as_view(), name='subject_add'),
    path('subjects/<int:pk>/edit/', SubjectUpdateView.as_view(), name='subject_edit'),
    path('subjects/<int:pk>/delete/', SubjectDeleteView.as_view(), name='subject_delete'),
    path('subjects/<int:pk>/assign/', AssignSubjectView.as_view(), name='subject_assign'),
    path('subjects/<int:pk>/toggle-active/', ToggleSubjectActiveView.as_view(), name='toggle_subject_active'),

    path('settings/', SystemSettingsView.as_view(), name='system_settings'),


    path('exams/', ExamListView.as_view(), name='exam_list'),
    path('exams/create/', ExamCreateView.as_view(), name='exam_create'),
    path('exams/<int:pk>/update/', ExamUpdateView.as_view(), name='exam_update'),
    path('exams/<int:pk>/delete/', ExamDeleteView.as_view(), name='exam_delete'),
    path('general-exams/', GeneralExamListView.as_view(), name='general_exam_list'),
    path('general-exams/create/', GeneralExamCreateView.as_view(), name='general_exam_create'),
    path('general-exams/<int:pk>/update/', GeneralExamUpdateView.as_view(), name='general_exam_update'),
    path('general-exams/<int:pk>/delete/', GeneralExamDeleteView.as_view(), name='general_exam_delete'),


    path('manage-results/', ManageResultsView.as_view(), name='manage_results'),
    path('api/classes/', get_classes, name='api_classes'),
    path('api/exams/', get_exams, name='api_exams'),
    path('api/results/', get_results, name='api_results'),
    path('api/save-grade/', save_grade, name='api_save_grade'),



]