from django.urls import path
from .views import (
    AddTeacherView, CustomLoginView, CustomLogoutView, DashboardView, DeleteTeacherView, EditTeacherView,
    GenericDashboardView, TeacherDashboardView, SecretaryDashboardView, TeacherDetailView,
    TeacherListView, ToggleTeacherActiveView
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
]