from django import forms
from django.contrib.auth import get_user_model
from result_system.models import Teacher, TeacherSubject, Class, Subject, ClassSubject

User = get_user_model()









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
            self.fields['subjects'].initial = self.instance.subjects.all()

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_subjects(instance)
        return instance

    def save_subjects(self, instance):
        instance.subjects.set(self.cleaned_data['subjects'])









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