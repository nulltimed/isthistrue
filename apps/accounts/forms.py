from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class RegisterForm(UserCreationForm):
    birth_date = forms.DateField(label='Fecha de nacimiento',
                                 widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'birth_date')

    def clean_birth_date(self):
        from datetime import date
        bd = self.cleaned_data['birth_date']
        today = date.today()
        age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
        if age < 14:  # minimo legal LOPDGDD art. 7
            raise forms.ValidationError('Debes tener al menos 14 años para registrarte.')
        return bd
