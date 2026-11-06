from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User

class RegisterForm(UserCreationForm):
    email = forms.EmailField(label='Email', required=True)

    birth_date = forms.DateField(label='Fecha de nacimiento',
                                 widget=forms.DateInput(attrs={'type': 'date'}))
    # 6.3 (orden de David, 2026-11-06): el registro pregunta quien eres, en dos
    # carriles. A la persona fisica NO se le pide ni investiga nada mas; a la
    # juridica, su nombre y su web (lo minimo que el escrutinio necesita).
    kind = forms.ChoiceField(
        label='Tipo de cuenta', initial='PERSON',
        choices=[('PERSON', 'Persona física'),
                 ('ORG', 'Persona jurídica (medio, ONG, empresa...)')],
        widget=forms.Select(attrs={'data-tip': 'Las personas jurídicas pasan un '
                                   'escrutinio automático; a las físicas no se les '
                                   'investiga nada.'}))
    org_name = forms.CharField(
        label='Nombre de la organización (solo personas jurídicas)',
        required=False, max_length=200,
        widget=forms.TextInput(attrs={'data-tip': 'El nombre con el que el '
                                      'escrutinio puede saber quién sois.'}))
    org_website = forms.URLField(
        label='Web de la organización (opcional)', required=False,
        widget=forms.URLInput(attrs={'data-tip': 'Si la dais, el escrutinio os '
                                     'confirma antes y mejor.'}))

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

    def clean(self):
        data = super().clean()
        if self.cleaned_data.get('kind') == 'ORG' and \
                not self.cleaned_data.get('org_name', '').strip():
            self.add_error('org_name', 'Una persona jurídica debe decir su nombre.')
        return data

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Ya existe una cuenta con este email.')
        return email

