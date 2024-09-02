from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.views.generic import TemplateView, RedirectView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404, render
from result_system.models import AcademicYear, ClassSubject, Exam, GeneralExam, Result, StudentSubject, Subject, SystemSettings, Teacher, Class, Student, TeacherSubject, User
from django.views.generic import ListView
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from .forms import AcademicYearForm, AssignSubjectForm, ClassForm, ExamForm, ExamSelectionForm, GeneralExamForm, StudentDocumentFormSet, StudentForm, StudentSubjectForm, SubjectForm, SystemSettingsForm, TeacherForm
from .mixins import SecretaryRequiredMixin

from django.db.models import Prefetch
from django.db import transaction
import json
from django.urls import reverse
from django.views import View
from django.db.models import Q



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
        context['enrolled_subjects'] = self.object.get_current_subjects().select_related('class_subject__subject')
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

    @transaction.atomic
    def form_valid(self, form):
        selected_subjects = form.cleaned_data['subjects']
        current_subjects = set(self.student.get_current_subjects().values_list('class_subject_id', flat=True))

        # Deactivate unselected subjects
        subjects_to_deactivate = current_subjects - set(selected_subjects)
        StudentSubject.objects.filter(
            student=self.student,
            class_subject_id__in=subjects_to_deactivate,
            academic_year=self.student.current_class.academic_year,
            is_active=True
        ).update(is_active=False)

        # Activate or create newly selected subjects
        for subject in selected_subjects:
            StudentSubject.objects.update_or_create(
                student=self.student,
                class_subject=subject,
                academic_year=self.student.current_class.academic_year,
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



class GradeCalculationView(TemplateView):
    template_name = 'users/grade_calculation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam_id = self.request.GET.get('exam_id')
        class_subject_id = self.request.GET.get('class_subject_id')
        
        if exam_id and class_subject_id:
            exam = get_object_or_404(Exam, pk=exam_id)
            class_subject = get_object_or_404(ClassSubject, pk=class_subject_id)
            results = Result.objects.filter(exam=exam, class_subject=class_subject)
            
            graded_results = []
            for result in results:
                graded_results.append({
                    'student': result.student,
                    'mark': result.mark,
                    'grade': result.calculate_grade()
                })
            
            context['exam'] = exam
            context['class_subject'] = class_subject
            context['graded_results'] = graded_results
        
        context['form'] = ExamSelectionForm()
        return context

    def post(self, request, *args, **kwargs):
        form = ExamSelectionForm(request.POST)
        if form.is_valid():
            exam = form.cleaned_data['exam']
            class_subject = form.cleaned_data['class_subject']
            return redirect(reverse('grade_calculation') + f'?exam_id={exam.id}&class_subject_id={class_subject.id}')
        return self.get(request, *args, **kwargs)





class ManageResultsView(LoginRequiredMixin, View):
    def get(self, request):
        academic_years = AcademicYear.objects.filter(school=request.user.school)
        context = {'academic_years': academic_years}
        return render(request, 'users/manage_results.html', context)

    def post(self, request):
        academic_year_id = request.POST.get('academic_year')
        class_id = request.POST.get('class')
        student_id = request.POST.get('student')

        if student_id == 'all':
            return redirect('bulk_edit_results', class_id=class_id)
        else:
            return redirect('edit_student_result', student_id=student_id)




class EditStudentResultView(LoginRequiredMixin, View):
    def get(self, request, student_id):
        student = get_object_or_404(Student, id=student_id, school=request.user.school)
        class_subjects = ClassSubject.objects.filter(class_obj=student.current_class)
        exams = Exam.objects.filter(school=request.user.school, academic_year=student.current_class.academic_year)
        results = Result.objects.filter(student=student, class_subject__in=class_subjects)

        context = {
            'student': student,
            'class_subjects': class_subjects,
            'exams': exams,
            'results': {(result.class_subject_id, result.exam_id): result for result in results}
        }
        return render(request, 'users/edit_student_result.html', context)

    def post(self, request, student_id):
        student = get_object_or_404(Student, id=student_id, school=request.user.school)
        class_subjects = ClassSubject.objects.filter(class_obj=student.current_class)
        exam_id = request.POST.get('exam')
        
        if not exam_id:
            messages.error(request, "Please select an exam.")
            return redirect('edit_student_result', student_id=student_id)

        exam = get_object_or_404(Exam, id=exam_id, school=request.user.school)

        with transaction.atomic():
            for class_subject in class_subjects:
                mark = request.POST.get(f'mark_{class_subject.id}')
                if mark:
                    Result.objects.update_or_create(
                        student=student,
                        class_subject=class_subject,
                        exam=exam,
                        defaults={'mark': mark, 'created_by': request.user}
                    )

        messages.success(request, f"Results updated successfully for {student.get_full_name()}")
        return redirect('edit_student_result', student_id=student_id)




class BulkEditResultsView(LoginRequiredMixin, View):
    def get(self, request, class_id):
        class_obj = get_object_or_404(Class, id=class_id, school=request.user.school)
        students = Student.objects.filter(current_class=class_obj)
        class_subjects = ClassSubject.objects.filter(class_obj=class_obj)
        exams = Exam.objects.filter(school=request.user.school, academic_year=class_obj.academic_year)
        results = Result.objects.filter(student__in=students, class_subject__in=class_subjects)

        context = {
            'class': class_obj,
            'students': students,
            'class_subjects': class_subjects,
            'exams': exams,
            'results': {(result.student_id, result.class_subject_id, result.exam_id): result for result in results}
        }
        return render(request, 'users/bulk_edit_results.html', context)

    def post(self, request, class_id):
        class_obj = get_object_or_404(Class, id=class_id, school=request.user.school)
        students = Student.objects.filter(current_class=class_obj)
        class_subjects = ClassSubject.objects.filter(class_obj=class_obj)
        exam_id = request.POST.get('exam')

        if not exam_id:
            messages.error(request, "Please select an exam.")
            return redirect('bulk_edit_results', class_id=class_id)

        exam = get_object_or_404(Exam, id=exam_id, school=request.user.school)

        with transaction.atomic():
            for student in students:
                for class_subject in class_subjects:
                    mark = request.POST.get(f'mark_{student.id}_{class_subject.id}')
                    if mark:
                        Result.objects.update_or_create(
                            student=student,
                            class_subject=class_subject,
                            exam=exam,
                            defaults={'mark': mark, 'created_by': request.user}
                        )

        messages.success(request, f"Results updated successfully for {class_obj.name}")
        return redirect('bulk_edit_results', class_id=class_id)

        
def get_classes(request):
    academic_year_id = request.GET.get('academic_year_id')
    classes = Class.objects.filter(academic_year_id=academic_year_id, school=request.user.school)
    return JsonResponse(list(classes.values('id', 'name')), safe=False)

def get_students(request):
    class_id = request.GET.get('class_id')
    students = Student.objects.filter(current_class_id=class_id, school=request.user.school)
    return JsonResponse(list(students.values('id', 'first_name', 'last_name')), safe=False)