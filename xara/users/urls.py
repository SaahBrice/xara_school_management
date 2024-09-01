from django.urls import path
from .views import (
    AddTeacherView, ClassCreateView, ClassDeleteView, ClassListView, ClassUpdateView, CustomLoginView, CustomLogoutView, DashboardView, DeleteTeacherView, EditTeacherView,
    GenericDashboardView, ManageStudentSubjectsView, StudentDeleteView, TeacherDashboardView, SecretaryDashboardView, TeacherDetailView,
    TeacherListView, ToggleTeacherActiveView, StudentCreateView, StudentDetailView, StudentUpdateView, StudentListView
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
]