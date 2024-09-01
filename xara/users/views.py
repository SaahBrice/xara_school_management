from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, RedirectView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
from result_system.models import ClassSubject, Subject, Teacher, Class, Student, TeacherSubject, User
from django.views.generic import ListView
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from .forms import ClassForm, TeacherForm
from .mixins import SecretaryRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch
from django.db import transaction
import json
from django.urls import reverse
from django.views import View


class CustomLoginView(LoginView):
    template_name = 'users/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Welcome, {self.request.user.get_full_name()}!')
        return response

    def form_invalid(self, form):
        for error in form.non_field_errors():
            messages.error(self.request, error)
        return super().form_invalid(form)

    def get_success_url(self):
        user = self.request.user
        if user.user_type == 'T':
            return reverse_lazy('teacher_dashboard')
        elif user.user_type == 'S':
            return reverse_lazy('secretary_dashboard')
        else:
            return reverse_lazy('dashboard')

class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('landing_page')
    template_name = 'users/logout_confirm.html'

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return self.render_to_response(self.get_context_data())
        response = super().dispatch(request, *args, **kwargs)
        messages.info(request, 'You have been logged out.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Logout Confirmation'
        return context

class DashboardView(LoginRequiredMixin, RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        user = self.request.user
        if user.user_type == 'T':
            return reverse_lazy('teacher_dashboard')
        elif user.user_type == 'S':
            return reverse_lazy('secretary_dashboard')
        else:
            return reverse_lazy('generic_dashboard')

class GenericDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'users/dashboard.html'

class UserTypeRequiredMixin(UserPassesTestMixin):
    required_user_type = None

    def test_func(self):
        return self.request.user.user_type == self.required_user_type

    def handle_no_permission(self):
        messages.error(self.request, 'You do not have permission to access this page.')
        return redirect('dashboard')

class TeacherDashboardView(LoginRequiredMixin, UserTypeRequiredMixin, TemplateView):
    template_name = 'users/teacher_dashboard.html'
    required_user_type = 'T'




class SecretaryDashboardView(LoginRequiredMixin, UserTypeRequiredMixin, TemplateView):
    template_name = 'users/secretary_dashboard.html'
    required_user_type = 'S'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['teacher_count'] = Teacher.objects.filter().count()
        context['class_count'] = Class.objects.filter().count()
        context['student_count'] = Student.objects.filter().count()
        return context


class TeacherListView(LoginRequiredMixin, SecretaryRequiredMixin, ListView):
    model = Teacher
    template_name = 'users/teacher_list.html'
    context_object_name = 'teachers'
    paginate_by = 20  # Add pagination for better performance with large datasets

    def get_queryset(self):
        return Teacher.objects.select_related('user').prefetch_related(
            Prefetch('teaching_assignments', queryset=TeacherSubject.objects.select_related('subject', 'class_obj'))
        ).order_by('user__last_name', 'user__first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_teachers'] = self.get_queryset().count()
        return context


class AddTeacherView(SecretaryRequiredMixin, CreateView):
    form_class = TeacherForm
    template_name = 'users/add_teacher.html'
    success_url = reverse_lazy('teacher_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        user = form.save(commit=False)
        user.school = self.request.user.school
        user.user_type = User.TEACHER
        user.save()

        teacher = Teacher.objects.create(
            user=user,
            qualifications=form.cleaned_data['qualifications']
        )

        messages.success(
            self.request, 
            f"Teacher {user.get_full_name()} has been added successfully. "
            f"You may now assign them to classes and subjects."
        )

        return super().form_valid(form)


class EditTeacherView(UpdateView):
    model = Teacher
    form_class = TeacherForm
    template_name = 'users/edit_teacher.html'
    success_url = reverse_lazy('teacher_list')

    def get_object(self, queryset=None):
        return Teacher.objects.select_related('user').get(pk=self.kwargs['pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.object.user
        kwargs['school'] = self.request.user.school
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classes = Class.objects.filter(school=self.request.user.school)
        classes_data = []
        for class_obj in classes:
            subjects = Subject.objects.filter(classes__class_obj=class_obj)
            classes_data.append({
                'id': class_obj.id,
                'name': str(class_obj),
                'subjects': [{'id': subject.id, 'name': str(subject)} for subject in subjects]
            })
        context['classes_json'] = json.dumps(classes_data)
        context['initial_assignments'] = json.dumps(list(self.object.teaching_assignments.values_list('class_obj_id', 'subject_id')))
        return context

    @transaction.atomic
    def form_valid(self, form):
        user = form.save()
        self.object.qualifications = form.cleaned_data['qualifications']
        self.object.save()

        assignments = json.loads(self.request.POST.get('assignments', '[]'))
        TeacherSubject.objects.filter(teacher=self.object).delete()
        for assignment in assignments:
            TeacherSubject.objects.create(
                teacher=self.object,
                class_obj_id=assignment['class_id'],
                subject_id=assignment['subject_id']
            )
        messages.success(self.request, 'Teacher updated successfully.')
        return super().form_valid(form)

class DeleteTeacherView(SecretaryRequiredMixin, DeleteView):
    model = Teacher
    template_name = 'users/delete_teacher.html'
    success_url = reverse_lazy('teacher_list')

    def get_object(self, queryset=None):
        return Teacher.objects.select_related('user').get(pk=self.kwargs['pk'])

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        teacher = self.get_object()
        user = teacher.user
        response = super().delete(request, *args, **kwargs)
        user.delete()
        messages.success(self.request, 'Teacher deleted successfully.')
        return response


class TeacherDetailView(SecretaryRequiredMixin, DetailView):
    model = Teacher
    template_name = 'users/teacher_detail.html'
    context_object_name = 'teacher'

    def get_queryset(self):
        return Teacher.objects.filter(user__school=self.request.user.school).select_related('user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['teaching_assignments'] = TeacherSubject.objects.filter(
            teacher=self.object
        ).select_related('subject', 'class_obj').order_by('class_obj__name', 'subject__name')
        return context



class ToggleTeacherActiveView(View):
    def post(self, request, pk):
        teacher = get_object_or_404(Teacher, pk=pk)
        teacher.user.toggle_active()
        status = "activated" if teacher.user.is_active else "deactivated"
        messages.success(request, f"Teacher {teacher.user.get_full_name()} has been {status}.")
        return redirect(reverse('teacher_list'))





class ClassListView(SecretaryRequiredMixin, ListView):
    model = Class
    template_name = 'users/class_list.html'
    context_object_name = 'classes'
    paginate_by = 20  # Number of classes per page

    def get_queryset(self):
        return Class.objects.filter(school=self.request.user.school).select_related('academic_year').prefetch_related(
            Prefetch('subjects', queryset=ClassSubject.objects.select_related('subject'))
        ).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_classes'] = self.get_queryset().count()
        return context





class ClassCreateView(SecretaryRequiredMixin, CreateView):
    model = Class
    form_class = ClassForm
    template_name = 'users/class_form.html'
    success_url = reverse_lazy('class_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        return kwargs

    def form_valid(self, form):
        form.instance.school = self.request.user.school
        messages.success(self.request, 'Class created successfully.')
        return super().form_valid(form)

class ClassUpdateView(SecretaryRequiredMixin, UpdateView):
    model = Class
    form_class = ClassForm
    template_name = 'users/class_form.html'
    success_url = reverse_lazy('class_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Class updated successfully.')
        return super().form_valid(form)

class ClassDeleteView(SecretaryRequiredMixin, DeleteView):
    model = Class
    template_name = 'users/class_confirm_delete.html'
    success_url = reverse_lazy('class_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Class deleted successfully.')
        return super().delete(request, *args, **kwargs)