import json
from django import forms
from django.contrib.auth import get_user_model
from result_system.models import AcademicYear, Exam, GeneralExam, Student, StudentDocument, StudentSubject, SystemSettings, Teacher, Class, Subject, ClassSubject
from django.db import transaction



User = get_user_model()


class StudentSubjectForm(forms.Form):
    subjects = forms.ModelMultipleChoiceField(
        queryset=ClassSubject.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
        if self.student and self.student.current_class:
            self.fields['subjects'].queryset = self.student.current_class.subjects.filter(is_active=True)
            self.initial['subjects'] = StudentSubject.get_active_subjects_for_student(
                self.student, self.student.current_class.academic_year
            ).values_list('class_subject_id', flat=True)

            
class StudentDocumentForm(forms.ModelForm):
    class Meta:
        model = StudentDocument
        fields = ['document_type', 'file', 'description']

StudentDocumentFormSet = forms.inlineformset_factory(
    Student, StudentDocument, form=StudentDocumentForm,
    extra=1, can_delete=True
)

class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['first_name', 'last_name', 'current_class', 'date_of_birth', 'gender',
                  'address', 'email', 'phone', 'parent_name', 'parent_contact',
                  'parent_email', 'parent_address', 'picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'gender': forms.Select(choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')]),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if school:
            self.fields['current_class'].queryset = Class.objects.filter(school=school)






class ClassForm(forms.ModelForm):
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Class
        fields = ['name', 'academic_year', 'capacity']

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if self.school:
            self.fields['academic_year'].queryset = self.school.academic_years.all()
            self.fields['subjects'].queryset = Subject.objects.filter(school=self.school)

        if self.instance.pk:
            self.fields['subjects'].initial = Subject.objects.filter(
                classes__class_obj=self.instance,
                classes__is_active=True
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_subjects(instance)
        return instance

    def save_subjects(self, instance):
        if self.cleaned_data['subjects']:
            with transaction.atomic():
                current_subjects = set(ClassSubject.objects.filter(
                    class_obj=instance
                ).values_list('subject_id', flat=True))
                
                new_subjects = set(self.cleaned_data['subjects'].values_list('id', flat=True))

                # Deactivate subjects that are no longer selected
                subjects_to_deactivate = current_subjects - new_subjects
                ClassSubject.objects.filter(
                    class_obj=instance,
                    subject_id__in=subjects_to_deactivate
                ).update(is_active=False)

                # Add new subjects or reactivate existing ones
                subjects_to_add_or_reactivate = new_subjects - current_subjects
                for subject_id in subjects_to_add_or_reactivate:
                    subject = Subject.objects.get(id=subject_id)
                    ClassSubject.objects.update_or_create(
                        class_obj=instance,
                        subject=subject,
                        defaults={'is_active': True, 'credit': subject.default_credit}
                    )

                # Reactivate subjects that were previously deactivated
                subjects_to_reactivate = new_subjects & current_subjects
                ClassSubject.objects.filter(
                    class_obj=instance,
                    subject_id__in=subjects_to_reactivate
                ).update(is_active=True)









class TeacherForm(forms.ModelForm):
    qualifications = forms.CharField(widget=forms.Textarea, required=False)
    password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone']

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            try:
                teacher = self.instance.teacher
                self.fields['qualifications'].initial = teacher.qualifications
            except Teacher.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['year', 'start_date', 'end_date', 'is_current']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        is_current = cleaned_data.get('is_current')

        if start_date and end_date and start_date >= end_date:
            raise forms.ValidationError("End date must be after start date.")

        if is_current:
            existing_current = AcademicYear.objects.filter(school=self.school, is_current=True).exclude(pk=self.instance.pk)
            if existing_current.exists():
                raise forms.ValidationError("Another academic year is already set as current.")

        return cleaned_data






class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'default_credit', 'description', 'subject_type']

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data['code']
        if Subject.objects.filter(school=self.school, code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A subject with this code already exists in your school.")
        return code

class AssignSubjectForm(forms.Form):
    classes = forms.ModelMultipleChoiceField(
        queryset=Class.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    credit = forms.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        
    )

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        self.subject = kwargs.pop('subject', None)
        super().__init__(*args, **kwargs)
        
        if self.school:
            self.fields['classes'].queryset = Class.objects.filter(
                school=self.school,
                academic_year__is_current=True
            )
        
        if self.subject:
            self.fields['credit'].initial = self.subject.default_credit
            self.initial['classes'] = self.subject.get_classes().values_list('class_obj__id', flat=True)



class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = ['school_initials', 'academic_year_format', 'max_students_per_class', 'grading_system', 'default_pass_mark']
        widgets = {
            'grading_system': forms.Textarea(attrs={'rows': 20, 'style': 'font-family: monospace; font-size: 14px;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and isinstance(self.instance.grading_system, dict):
            self.initial['grading_system'] = json.dumps(self.instance.grading_system, indent=2)

    def clean_grading_system(self):
        grading_system = self.cleaned_data['grading_system']
        try:
            # Parse the JSON string into a Python dict
            return json.loads(grading_system)
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON format for grading system.")



class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'academic_year', 'start_date', 'end_date', 'is_active', 'max_score']

class GeneralExamForm(forms.ModelForm):
    class Meta:
        model = GeneralExam
        fields = ['name', 'academic_year', 'exams', 'start_date', 'end_date']



class ExamSelectionForm(forms.Form):
    exam = forms.ModelChoiceField(queryset=Exam.objects.all())
    class_subject = forms.ModelChoiceField(queryset=ClassSubject.objects.all())

