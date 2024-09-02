from django import forms
from django.contrib.auth import get_user_model
from result_system.models import AcademicYear, Student, StudentDocument, Teacher, TeacherSubject, Class, Subject, ClassSubject

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
            self.fields['subjects'].queryset = self.student.current_class.subjects.all()
            self.initial['subjects'] = self.student.get_current_subjects().values_list('class_subject_id', flat=True)

            
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
            self.fields['subjects'].initial = Subject.objects.filter(classes__class_obj=self.instance)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_subjects(instance)
        return instance

    def save_subjects(self, instance):
        # Clear existing subjects
        ClassSubject.objects.filter(class_obj=instance).delete()
        
        # Add new subjects
        for subject in self.cleaned_data['subjects']:
            ClassSubject.objects.create(class_obj=instance, subject=subject)









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