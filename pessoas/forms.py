# satilo/pessoas/forms.py
from django import forms
from .models import Pessoa

class PessoaForm(forms.ModelForm):
    class Meta:
        model = Pessoa
        fields = '__all__'
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'data_falecimento': forms.DateInput(attrs={'type': 'date'}),
            # Não adicione 'genero': forms.Select(...) aqui, deixe o Django cuidar disso
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