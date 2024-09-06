from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.views.generic import TemplateView, RedirectView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from result_system.models import AcademicYear, ClassSubject, Exam, GeneralExam, GradeSheet, StudentSubject, Subject, SubjectGrade, SystemSettings, Teacher, Class, Student, TeacherSubject, User
from django.views.generic import ListView
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from .forms import AcademicYearForm, AssignSubjectForm, ClassForm, ExamForm, GeneralExamForm, StudentDocumentFormSet, StudentForm, StudentSubjectForm, SubjectForm, SystemSettingsForm, TeacherForm
from .mixins import SecretaryRequiredMixin

from django.db.models import Prefetch
from django.db import transaction
import json
from django.urls import reverse
from django.views import View

from django.core.serializers.json import DjangoJSONEncoder

from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt


from django.db.models import Sum, Max, Min, Avg, Count, Q, Count,Case,When, F, FloatField, IntegerField, Value
from django.db.models.functions import Coalesce
from django.db.models.expressions import ExpressionWrapper



from django.core.exceptions import ValidationError

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP



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
            Prefetch('subjects', queryset=ClassSubject.objects.select_related('subject').filter(is_active=True))
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



class StudentListView(SecretaryRequiredMixin, ListView):
    model = Student
    template_name = 'users/student_list.html'
    context_object_name = 'students'
    paginate_by = 20

    def get_queryset(self):
        queryset = Student.objects.filter(school=self.request.user.school).select_related('current_class')
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(matricula_code__icontains=search_query)
            )
        return queryset.order_by('last_name', 'first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_students'] = self.get_queryset().count()
        return context

class StudentCreateView(SecretaryRequiredMixin, CreateView):
    model = Student
    form_class = StudentForm
    template_name = 'users/student_form.html'
    success_url = reverse_lazy('student_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['documents'] = StudentDocumentFormSet(self.request.POST, self.request.FILES)
        else:
            data['documents'] = StudentDocumentFormSet()
        return data

    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()
        documents = context['documents']
        form.instance.school = self.request.user.school
        self.object = form.save()
        if documents.is_valid():
            documents.instance = self.object
            documents.save()
        messages.success(self.request, 'Student added successfully.')
        return super().form_valid(form)

class StudentUpdateView(SecretaryRequiredMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = 'users/student_form.html'
    success_url = reverse_lazy('student_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        return kwargs

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['documents'] = StudentDocumentFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            data['documents'] = StudentDocumentFormSet(instance=self.object)
        return data

    @transaction.atomic
    def form_valid(self, form):
        context = self.get_context_data()
        documents = context['documents']
        self.object = form.save()
        if documents.is_valid():
            documents.instance = self.object
            documents.save()
        messages.success(self.request, 'Student updated successfully.')
        return super().form_valid(form)

class StudentDetailView(SecretaryRequiredMixin, DetailView):
    model = Student
    template_name = 'users/student_detail.html'
    context_object_name = 'student'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['documents'] = self.object.documents.all()
        context['enrolled_subjects'] = self.object.get_current_subjects().select_related('class_subject__subject').filter(class_subject__is_active=True)
        return context

class StudentDeleteView(SecretaryRequiredMixin, DeleteView):
    model = Student
    template_name = 'users/student_confirm_delete.html'
    success_url = reverse_lazy('student_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Student deleted successfully.')
        return super().delete(request, *args, **kwargs)



class ManageStudentSubjectsView(SecretaryRequiredMixin, FormView):
    form_class = StudentSubjectForm
    template_name = 'users/manage_student_subjects.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.student = get_object_or_404(Student, pk=self.kwargs['pk'])
        kwargs['student'] = self.student
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['student'] = self.student
        return context

    def get_success_url(self):
        return reverse_lazy('student_detail', kwargs={'pk': self.student.pk})

    def form_valid(self, form):
        selected_subjects = form.cleaned_data['subjects']
        current_academic_year = self.student.current_class.academic_year

        with transaction.atomic():
            # Get all active subjects for the student
            current_subjects = set(StudentSubject.get_active_subjects_for_student(
                self.student, current_academic_year
            ).values_list('class_subject_id', flat=True))

            # Deactivate unselected subjects
            subjects_to_deactivate = current_subjects - set(selected_subjects)
            StudentSubject.objects.filter(
                student=self.student,
                class_subject_id__in=subjects_to_deactivate,
                academic_year=current_academic_year
            ).update(is_active=False)

            # Activate or create newly selected subjects
            for subject in selected_subjects:
                StudentSubject.objects.update_or_create(
                    student=self.student,
                    class_subject=subject,
                    academic_year=current_academic_year,
                    defaults={'is_active': True}
                )

        messages.success(self.request, "Student subjects updated successfully.")
        return super().form_valid(form)


class AcademicYearListView(SecretaryRequiredMixin, ListView):
    model = AcademicYear
    template_name = 'users/academic_year_list.html'
    context_object_name = 'academic_years'

    def get_queryset(self):
        return AcademicYear.objects.filter(school=self.request.user.school).order_by('-year')

class AcademicYearCreateView(SecretaryRequiredMixin, CreateView):
    model = AcademicYear
    form_class = AcademicYearForm
    template_name = 'users/academic_year_form.html'
    success_url = reverse_lazy('academic_year_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        return kwargs

    def form_valid(self, form):
        form.instance.school = self.request.user.school
        messages.success(self.request, 'Academic Year created successfully.')
        return super().form_valid(form)

class AcademicYearUpdateView(SecretaryRequiredMixin, UpdateView):
    model = AcademicYear
    form_class = AcademicYearForm
    template_name = 'users/academic_year_form.html'
    success_url = reverse_lazy('academic_year_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Academic Year updated successfully.')
        return super().form_valid(form)

class AcademicYearDeleteView(SecretaryRequiredMixin, DeleteView):
    model = AcademicYear
    template_name = 'users/academic_year_confirm_delete.html'
    success_url = reverse_lazy('academic_year_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Academic Year deleted successfully.')
        return super().delete(request, *args, **kwargs)

class SetCurrentAcademicYearView(SecretaryRequiredMixin, View):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        academic_year = get_object_or_404(AcademicYear, pk=kwargs['pk'], school=request.user.school)
        AcademicYear.objects.filter(school=request.user.school).update(is_current=False)
        academic_year.is_current = True
        academic_year.save()
        messages.success(request, f'{academic_year.year} set as the current academic year.')
        return redirect('academic_year_list')


class ToggleStudentActiveView(SecretaryRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        student = get_object_or_404(Student, pk=kwargs['pk'], school=request.user.school)
        student.toggle_active()
        status = "activated" if student.is_active else "deactivated"
        messages.success(request, f"Student {student.get_full_name()} has been {status}.")
        return redirect('student_list')





class SubjectListView(SecretaryRequiredMixin, ListView):
    model = Subject
    template_name = 'users/subject_list.html'
    context_object_name = 'subjects'
    paginate_by = 20

    def get_queryset(self):
        return Subject.objects.filter(school=self.request.user.school)

class SubjectCreateView(SecretaryRequiredMixin, CreateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'users/subject_form.html'
    success_url = reverse_lazy('subject_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        return kwargs

    def form_valid(self, form):
        form.instance.school = self.request.user.school
        messages.success(self.request, 'Subject created successfully.')
        return super().form_valid(form)

class SubjectUpdateView(SecretaryRequiredMixin, UpdateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'users/subject_form.html'
    success_url = reverse_lazy('subject_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Subject updated successfully.')
        return super().form_valid(form)

class SubjectDeleteView(SecretaryRequiredMixin, DeleteView):
    model = Subject
    template_name = 'users/subject_confirm_delete.html'
    success_url = reverse_lazy('subject_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Subject deleted successfully.')
        return super().delete(request, *args, **kwargs)

class AssignSubjectView(SecretaryRequiredMixin, FormView):
    form_class = AssignSubjectForm
    template_name = 'users/assign_subject.html'
    success_url = reverse_lazy('subject_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['school'] = self.request.user.school
        kwargs['subject'] = get_object_or_404(Subject, pk=self.kwargs['pk'], school=self.request.user.school)
        return kwargs

    def form_valid(self, form):
        subject = get_object_or_404(Subject, pk=self.kwargs['pk'], school=self.request.user.school)
        selected_classes = form.cleaned_data['classes']
        credit = form.cleaned_data['credit']

        with transaction.atomic():
            # Remove subject from unselected classes
            ClassSubject.objects.filter(subject=subject).exclude(class_obj__in=selected_classes).delete()

            # Add or update subject for selected classes
            for class_obj in selected_classes:
                ClassSubject.objects.update_or_create(
                    subject=subject,
                    class_obj=class_obj,
                    defaults={'credit': credit}
                )

        messages.success(self.request, f'{subject.name} has been assigned to the selected classes.')
        return super().form_valid(form)

class ToggleSubjectActiveView(SecretaryRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        subject = get_object_or_404(Subject, pk=kwargs['pk'], school=request.user.school)
        subject.toggle_active()
        status = "activated" if subject.is_active else "deactivated"
        messages.success(request, f"Subject {subject.name} has been {status}.")
        return redirect('subject_list')




class SystemSettingsView(SecretaryRequiredMixin, FormView):
    template_name = 'users/system_settings.html'
    form_class = SystemSettingsForm
    success_url = reverse_lazy('system_settings')


    def get_form(self):
        try:
            instance = SystemSettings.objects.get(school=self.request.user.school)
        except SystemSettings.DoesNotExist:
            instance = None
        
        if self.request.method == 'POST':
            return self.form_class(self.request.POST, instance=instance)
        else:
            return self.form_class(instance=instance)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_fields'] = [
            (field.label, field.name, field.value() if field.value() is not None else '', field.help_text)
            for field in self.get_form()
        ]
        return context

    def form_valid(self, form):
        try:
            form.instance.school = self.request.user.school
            form.save()
            messages.success(self.request, 'System settings updated successfully.')
        except json.JSONDecodeError:
            messages.error(self.request, 'Invalid JSON format in grading system.')
            return self.form_invalid(form)
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'There was an error updating the system settings. Please check the form and try again.')
        return super().form_invalid(form)




class ExamListView(ListView):
    model = Exam
    template_name = 'users/exam_list.html'
    context_object_name = 'exams'

class ExamCreateView(CreateView):
    model = Exam
    form_class = ExamForm
    template_name = 'users/exam_form.html'
    success_url = reverse_lazy('exam_list')

    def form_valid(self, form):
        form.instance.school = self.request.user.school
        messages.success(self.request, 'Exam created successfully.')
        return super().form_valid(form)

class ExamUpdateView(UpdateView):
    model = Exam
    form_class = ExamForm
    template_name = 'users/exam_form.html'
    success_url = reverse_lazy('exam_list')

    def form_valid(self, form):
        messages.success(self.request, 'Exam updated successfully.')
        return super().form_valid(form)

class ExamDeleteView(DeleteView):
    model = Exam
    template_name = 'users/exam_confirm_delete.html'
    success_url = reverse_lazy('exam_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Exam deleted successfully.')
        return super().delete(request, *args, **kwargs)

class GeneralExamListView(ListView):
    model = GeneralExam
    template_name = 'users/general_exam_list.html'
    context_object_name = 'general_exams'

class GeneralExamCreateView(CreateView):
    model = GeneralExam
    form_class = GeneralExamForm
    template_name = 'users/general_exam_form.html'
    success_url = reverse_lazy('general_exam_list')

    def form_valid(self, form):
        form.instance.school = self.request.user.school
        messages.success(self.request, 'General Exam created successfully.')
        return super().form_valid(form)

class GeneralExamUpdateView(UpdateView):
    model = GeneralExam
    form_class = GeneralExamForm
    template_name = 'users/general_exam_form.html'
    success_url = reverse_lazy('general_exam_list')

    def form_valid(self, form):
        messages.success(self.request, 'General Exam updated successfully.')
        return super().form_valid(form)

class GeneralExamDeleteView(DeleteView):
    model = GeneralExam
    template_name = 'users/general_exam_confirm_delete.html'
    success_url = reverse_lazy('general_exam_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'General Exam deleted successfully.')
        return super().delete(request, *args, **kwargs)





class ManageResultsView(LoginRequiredMixin, SecretaryRequiredMixin, TemplateView):
    template_name = 'users/manage_results.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['academic_years'] = AcademicYear.objects.filter(school=self.request.user.school)
        return context


def get_classes(request):
    academic_year_id = request.GET.get('academic_year')
    classes = Class.objects.filter(academic_year_id=academic_year_id, school=request.user.school)
    return JsonResponse(list(classes.values('id', 'name')), safe=False)

def get_exams(request):
    academic_year_id = request.GET.get('academic_year')
    exams = Exam.objects.filter(academic_year_id=academic_year_id, school=request.user.school)
    return JsonResponse(list(exams.values('id', 'name')), safe=False)

def get_results(request):
    academic_year_id = request.GET.get('academic_year')
    class_id = request.GET.get('class')
    exam_id = request.GET.get('exam')
    
    class_obj = Class.objects.get(id=class_id)
    exam = Exam.objects.get(id=exam_id)
    
    subjects = ClassSubject.objects.filter(class_obj=class_obj).select_related('subject')

    # Fetch teacher assignments
    teacher_assignments = TeacherSubject.objects.filter(
        class_obj=class_obj,
        subject__in=subjects.values('subject')
    ).select_related('teacher__user', 'subject')

    # Create a dictionary to easily lookup teacher for each subject
    teacher_lookup = {ta.subject.id: ta.teacher.user.get_full_name() for ta in teacher_assignments}

    grade_sheets = GradeSheet.objects.filter(
        academic_year_id=academic_year_id,
        class_obj_id=class_id,
        exam_id=exam_id
    ).select_related('student').prefetch_related('subject_grades')
    
    subject_stats = SubjectGrade.objects.filter(
        grade_sheet__exam_id=exam_id,
        grade_sheet__class_obj_id=class_id
    ).values('class_subject__subject__id').annotate(
        max_score=Max('score'),
        min_score=Min('score'),
        avg_score=Avg('score'),
        num_sat=Count('id'),
        num_passed=Sum(Case(When(score__gte=10, then=1), default=0, output_field=IntegerField())),
        percentage_passed=ExpressionWrapper(
            Case(
                When(num_sat__gt=0, then=F('num_passed') * 100.0 / F('num_sat')),
                default=Value(0.0)
            ),
            output_field=FloatField()
            )
    )

    subject_data = []
    for subject in subjects:
        stats = next((s for s in subject_stats if s['class_subject__subject__id'] == subject.subject.id), {})
        subject_data.append({
            'id': subject.subject.id,
            'name': subject.subject.name,
            'credit': subject.credit,
            'teacher': teacher_lookup.get(subject.subject.id, 'Not Assigned'),
            'max_score': stats.get('max_score'),
            'min_score': stats.get('min_score'),
            'avg_score': stats.get('avg_score'),
            'num_sat': stats.get('num_sat', 0),
            'num_passed': stats.get('num_passed', 0),
            'percentage_passed': stats.get('percentage_passed', 0)
        })

    students_data = []
    for grade_sheet in grade_sheets:
        grades = []
        for subject in subjects:
            grade = next((g for g in grade_sheet.subject_grades.all() if g.class_subject.subject.id == subject.subject.id), None)
            grades.append({
                'score': grade.score if grade else None,
                'rank': grade.rank if grade else None
            })
        
        students_data.append({
            'id': grade_sheet.student.id,
            'name': grade_sheet.student.get_full_name(),
            'grades': grades,
            'total': grade_sheet.total_score,
            'creditsAttempted': grade_sheet.credits_attempted,
            'average': grade_sheet.average,
            'remark': grade_sheet.remark,
            'rank': grade_sheet.rank
        })

    overall_stats = {
        'num_students': grade_sheets.count(),
        'num_passes': grade_sheets.filter(remark='PASSED').count(),
        'class_average': grade_sheets.aggregate(Avg('average'))['average__avg'] or 0,
        'overall_percentage_pass': (grade_sheets.filter(remark='PASSED').count() / grade_sheets.count()) * 100 if grade_sheets.count() > 0 else 0
    }

    return JsonResponse({
        'subjects': subject_data,
        'students': students_data,
        'overall_stats': overall_stats
    })



@require_http_methods(["POST"])
@csrf_exempt
def save_grade(request):
    data = json.loads(request.body)
    student_id = data.get('student_id')
    subject_id = data.get('subject_id')
    score = data.get('score')
    exam_id = data.get('exam_id')

    try:
        with transaction.atomic():
            grade_sheet = GradeSheet.objects.get(
                student_id=student_id,
                exam_id=exam_id
            )
            class_subject = ClassSubject.objects.get(
                class_obj=grade_sheet.class_obj,
                subject_id=subject_id
            )
            
            # Convert score to Decimal, round to 2 decimal places, and validate
            try:
                score = Decimal(score).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if score < 0 or score > 20:  # Adjust this range as needed
                    raise ValidationError("Score must be between 0 and 20")
            except (InvalidOperation, ValidationError) as e:
                return JsonResponse({'success': False, 'error': str(e)})

            subject_grade, created = SubjectGrade.objects.get_or_create(
                grade_sheet=grade_sheet,
                class_subject=class_subject,
                defaults={'score': score}
            )
            if not created:
                subject_grade.score = score
                subject_grade.save()

            # Recalculate GradeSheet
            grade_sheet.calculate_totals_and_average(prevent_recursive_save=True)

            # Recalculate ranks
            GradeSheet.bulk_update_ranks(grade_sheet.exam, grade_sheet.class_obj)
            SubjectGrade.bulk_update_ranks(grade_sheet.exam, grade_sheet.class_obj, class_subject)

        return JsonResponse({
            'success': True, 
            'rounded_score': float(score),
            'total_score': float(grade_sheet.total_score),
            'average': float(grade_sheet.average),
            'remark': grade_sheet.remark,
            'rank': grade_sheet.rank
        })
    except GradeSheet.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Grade sheet not found'})
    except ClassSubject.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Subject not found for this class'})
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"An unexpected error occurred: {str(e)}"})