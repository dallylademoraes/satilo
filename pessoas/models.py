# satilo/pessoas/models.py

from django.db import models
from datetime import date 

class Pessoa(models.Model):
    nome = models.CharField(max_length=100)
    data_nascimento = models.DateField(null=True, blank=True)
    data_falecimento = models.DateField(null=True, blank=True)
    genero = models.CharField(max_length=10, choices=[('M', 'Masculino'), ('F', 'Feminino')])
    pai = models.ForeignKey('self', null=True, blank=True, related_name='filhos_do_pai', on_delete=models.SET_NULL)
    mae = models.ForeignKey('self', null=True, blank=True, related_name='filhos_da_mae', on_delete=models.SET_NULL)
    foto = models.ImageField(upload_to='fotos_pessoas/', null=True, blank=True)
    historia_pessoal = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.nome

    def get_age(self):
        if self.data_nascimento:
            today = date.today()
            age = today.year - self.data_nascimento.year - ((today.month, today.day) < (self.data_nascimento.month, self.data_nascimento.day))
            return age
        return None

    def is_deceased(self):
        return self.data_falecimento is not None

    def get_relationship_to_user(self, user_pessoa):
        if not user_pessoa:
            return "Pessoa na Árvore" 

        if self == user_pessoa:
            return "Você"
        
        # 1. Pais diretos
        if self.pk == user_pessoa.pai_id:
            return "Seu Pai"
        if self.pk == user_pessoa.mae_id:
            return "Sua Mãe"
        
        # 2. Filhos diretos (da user_pessoa)
        if self.pai == user_pessoa or self.mae == user_pessoa:
            if self.genero == 'M':
                return "Seu Filho"
            else:
                return "Sua Filha"

        # 3. Irmãos
        # Verifica se têm pelo menos um pai ou uma mãe em comum
        has_common_parent = False
        if self.pai and user_pessoa.pai and self.pai == user_pessoa.pai:
            has_common_parent = True
        if self.mae and user_pessoa.mae and self.mae == user_pessoa.mae:
            has_common_parent = True
        
        if has_common_parent:
            return "Seu Irmão" if self.genero == 'M' else "Sua Irmã"

        # 4. Avós
        if user_pessoa.pai:
            if self.pk == user_pessoa.pai.pai_id:
                return "Seu Avô (paterno)"
            if self.pk == user_pessoa.pai.mae_id:
                return "Sua Avó (paterna)"
        if user_pessoa.mae:
            if self.pk == user_pessoa.mae.pai_id:
                return "Seu Avô (materno)"
            if self.pk == user_pessoa.mae.mae_id:
                return "Sua Avó (materna)"
        
        # 5. Tios (irmãos dos pais)
        # Primeiro, pegue os pais da user_pessoa
        parents_of_user = []
        if user_pessoa.pai: parents_of_user.append(user_pessoa.pai)
        if user_pessoa.mae: parents_of_user.append(user_pessoa.mae)

        for parent in parents_of_user:
            # Para cada pai, veja se 'self' é irmão desse pai
            if parent.pai and self.pk in [s.pk for s in parent.pai.filhos_do_pai.all() if s.pk != parent.pk and (not parent.mae or s.mae == parent.mae)]:
                return "Seu Tio (irmão do pai)" if self.genero == 'M' else "Sua Tia (irmã do pai)"
            if parent.mae and self.pk in [s.pk for s in parent.mae.filhos_da_mae.all() if s.pk != parent.pk and (not parent.pai or s.pai == parent.pai)]:
                return "Seu Tio (irmão da mãe)" if self.genero == 'M' else "Sua Tia (irmã da mãe)"
        
        # 6. Primos (filhos dos tios) - MUITO COMPLEXO
        # Para calcular primos de forma robusta, você precisaria de um algoritmo de travessia
        # de grafo que encontre o ancestral comum mais próximo e então determine as "distâncias"
        # Isso está além do escopo de um método simples aqui e seria melhor com uma biblioteca de grafo.

        return "Parentesco Indefinido" # Default