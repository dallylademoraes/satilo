# satilo/pessoas/forms.py

from django import forms
from .models import Pessoa
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

# Seus ESTADOS_BRASILEIROS_CHOICES
ESTADOS_BRASILEIROS_CHOICES = [
    ('', '---------- Selecione o Estado ----------'),
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
        # MUITO IMPORTANTE: EXCLUIR 'owner' E 'relacao' do formulário,
        # pois eles serão preenchidos programaticamente ou são campos calculados.
        # Se 'user' (OneToOneField) ainda estiver no seu models.py, adicione-o aqui também.
        exclude = ('owner',) # 'relacao' já foi removido do modelo na atualização anterior.
                             # Se você ainda tiver o campo 'user' (OneToOneField) no models.py
                             # de alguma forma, adicione-o aqui também: exclude = ('owner', 'user',)
        
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
        # A request precisa ser removida de kwargs antes de chamar super().__init__()
        # para que o ModelForm não tente processá-la como um dado do modelo.
        request = kwargs.pop('request', None) 
        super().__init__(*args, **kwargs)

        # Filtragem dos campos pai e mãe com base no usuário logado.
        # Self.instance existe se for um formulário de edição (UpdateView).
        # Request existe se for um formulário de criação (CreateView) ou se passada explicitamente.
        if self.instance and self.instance.pk: # Modo de edição
            # Filtra pai/mãe para serem do mesmo owner da pessoa que está sendo editada,
            # ou qualquer pessoa se o owner for superuser.
            if self.instance.owner and self.instance.owner.is_superuser:
                self.fields['pai'].queryset = Pessoa.objects.filter(genero='M').exclude(pk=self.instance.pk)
                self.fields['mae'].queryset = Pessoa.objects.filter(genero='F').exclude(pk=self.instance.pk)
            else:
                self.fields['pai'].queryset = Pessoa.objects.filter(genero='M', owner=self.instance.owner).exclude(pk=self.instance.pk)
                self.fields['mae'].queryset = Pessoa.objects.filter(genero='F', owner=self.instance.owner).exclude(pk=self.instance.pk)
        elif request and request.user.is_authenticated: # Modo de criação para usuário logado
            # Filtra pai/mãe para serem do mesmo owner do usuário logado que está criando.
            if request.user.is_superuser:
                self.fields['pai'].queryset = Pessoa.objects.filter(genero='M')
                self.fields['mae'].queryset = Pessoa.objects.filter(genero='F')
            else:
                self.fields['pai'].queryset = Pessoa.objects.filter(genero='M', owner=request.user)
                self.fields['mae'].queryset = Pessoa.objects.filter(genero='F', owner=request.user)
        else: # Cenário fallback (ex: admin sem request, ou não logado)
              # Pode ser um queryset vazio ou todos, dependendo da sua regra de negócio para não logados.
              # Mantendo o que você tinha, que é buscar todos, o que pode ser perigoso se não for superuser.
              # Se um usuário não logado tentar criar, ele não deve ver ninguém para pai/mãe.
            self.fields['pai'].queryset = Pessoa.objects.none() # Ninguém para escolher se não logado
            self.fields['mae'].queryset = Pessoa.objects.none()

        self.fields['pai'].empty_label = "----------"
        self.fields['mae'].empty_label = "----------"

        # Loop para adicionar classes Bootstrap a campos não especificados nos widgets
        for field_name, field in self.fields.items():
            # Evita sobrescrever os widgets já definidos na Meta
            if field_name not in self.Meta.widgets:
                if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.DateInput, forms.EmailInput, forms.NumberInput)):
                    field.widget.attrs['class'] = 'form-control'
                elif isinstance(field.widget, forms.Select):
                    field.widget.attrs['class'] = 'form-select'
                elif isinstance(field.widget, forms.CheckboxInput):
                    field.widget.attrs['class'] = 'form-check-input'
                elif isinstance(field.widget, forms.FileInput):
                    field.widget.attrs['class'] = 'form-control-file'

    # Removi o comentário do método clean(), você pode ativá-lo quando o problema principal estiver resolvido.
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

# Formulário para registro de usuário
class UserRegistrationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['password1'].widget.attrs['class'] = 'form-control'