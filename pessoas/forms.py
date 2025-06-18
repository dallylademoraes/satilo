# satilo/pessoas/forms.py

from django import forms
from .models import Pessoa
from django.contrib.auth.forms import UserCreationForm # Importa o formulário de criação de usuário do Django
from django.contrib.auth.models import User # Importa o modelo User padrão do Django

# ... (seus ESTADOS_BRASILEIROS_CHOICES aqui) ...
ESTADOS_BRASILEIROS_CHOICES = [
    ('', '---------- Selecione o Estado ----------'), # Opção vazia padrão
    ('AC', 'Acre'), ('AL', 'Alagoas'), ('AP', 'Amapá'), ('AM', 'Amazonas'),
    ('BA', 'Bahia'), ('CE', 'Ceará'), ('DF', 'Distrito Federal'), ('ES', 'Espírito Santo'),
    ('GO', 'Goiás'), ('MA', 'Maranhão'), ('MT', 'Mato Grosso'), ('MS', 'Mato Grosso do Sul'),
    ('MG', 'Minas Gerais'), ('PA', 'Pará'), ('PB', 'Paraíba'), ('PR', 'Paraná'),
    ('PE', 'Pernambuco'), ('PI', 'Piauí'), ('RJ', 'Rio de Janeiro'),
    ('RN', 'Rio Grande do Norte'), ('RS', 'Rio Grande do Sul'), ('RO', 'Rondônia'),
    ('RR', 'Roraima'), ('SC', 'Santa Catarina'), ('SP', 'São Paulo'),
    ('SE', 'Sergipe'), ('TO', 'Tocantins'),
]

class PessoaForm(forms.ModelForm):
    class Meta:
        model = Pessoa
        fields = '__all__'
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_falecimento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_falecimento_incerta': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: cerca de 1950, final dos anos 90'}),
            'local_nascimento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: São Paulo, SP - Brasil'}),
            'genero': forms.Select(attrs={'class': 'form-select'}),
            'pai': forms.Select(attrs={'class': 'form-select'}),
            'mae': forms.Select(attrs={'class': 'form-select'}),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'historia_pessoal': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'foto': forms.ClearableFileInput(attrs={'class': 'form-control-file'}),
            'estado_nascimento': forms.Select(choices=ESTADOS_BRASILEIROS_CHOICES, attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields['pai'].queryset = Pessoa.objects.filter(genero='M').exclude(pk=self.instance.pk)
            self.fields['mae'].queryset = Pessoa.objects.filter(genero='F').exclude(pk=self.instance.pk)
        else:
            self.fields['pai'].queryset = Pessoa.objects.filter(genero='M')
            self.fields['mae'].queryset = Pessoa.objects.filter(genero='F')

        self.fields['pai'].empty_label = "----------"
        self.fields['mae'].empty_label = "----------"

        for field_name, field in self.fields.items():
            if field_name not in self.Meta.widgets:
                if isinstance(field.widget, forms.TextInput) or \
                   isinstance(field.widget, forms.Textarea) or \
                   isinstance(field.widget, forms.DateInput) or \
                   isinstance(field.widget, forms.EmailInput) or \
                   isinstance(field.widget, forms.NumberInput):
                    field.widget.attrs['class'] = 'form-control'
                elif isinstance(field.widget, forms.Select):
                    field.widget.attrs['class'] = 'form-select'
                elif isinstance(field.widget, forms.CheckboxInput):
                    field.widget.attrs['class'] = 'form-check-input'
                elif isinstance(field.widget, forms.FileInput):
                    field.widget.attrs['class'] = 'form-control-file'

    def clean(self):
        cleaned_data = super().clean()
        data_falecimento = cleaned_data.get('data_falecimento')
        data_falecimento_incerta = cleaned_data.get('data_falecimento_incerta')

        if data_falecimento and data_falecimento_incerta:
            self.add_error('data_falecimento_incerta',
                           "Por favor, preencha apenas 'Data de Falecimento' ou 'Data de Falecimento (Incerta)', não ambos.")
            self.add_error('data_falecimento',
                           "Por favor, preencha apenas 'Data de Falecimento' ou 'Data de Falecimento (Incerta)', não ambos.")
        return cleaned_data

# NOVO: Formulário para registro de usuário
class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email') # Você pode adicionar mais campos se quiser estender o modelo User
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adiciona classes Bootstrap a campos que UserCreationForm cria automaticamente
        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['password1'].widget.attrs['class'] = 'form-control'