from django import forms
from django.contrib.auth import get_user_model
from result_system.models import Teacher, TeacherSubject, Class, Subject, ClassSubject

User = get_user_model()

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