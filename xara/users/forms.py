from django import forms
from django.contrib.auth import get_user_model
from result_system.models import Student, StudentDocument, Teacher, TeacherSubject, Class, Subject, ClassSubject

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