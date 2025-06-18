# satilo/pessoas/models.py

from django.db import models
from datetime import date
from collections import deque
from django.contrib.staticfiles.storage import staticfiles_storage

class Pessoa(models.Model):
    nome = models.CharField(max_length=100)
    data_nascimento = models.DateField(null=True, blank=True)
    data_falecimento = models.DateField(null=True, blank=True)
    data_falecimento_incerta = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Data de Falecimento (Incerta)",
        help_text="Ex: 'cerca de 1950', 'antes de 1990', 'final do século XX'. Preenche se a data exata for desconhecida."
    )
    genero = models.CharField(max_length=10, choices=[('M', 'Masculino'), ('F', 'Feminino')])
    pai = models.ForeignKey('self', null=True, blank=True, related_name='filhos_do_pai', on_delete=models.SET_NULL)
    mae = models.ForeignKey('self', null=True, blank=True, related_name='filhos_da_mae', on_delete=models.SET_NULL)
    foto = models.ImageField(upload_to='fotos_pessoas/', null=True, blank=True)
    historia_pessoal = models.TextField(null=True, blank=True)
    local_nascimento = models.CharField(max_length=200, blank=True, null=True, verbose_name="Local de Nascimento")
    # NOVO CAMPO: Estado de Nascimento
    estado_nascimento = models.CharField(
        max_length=2, # Ex: 'SP', 'MG', 'TO'
        blank=True,
        null=True,
        verbose_name="Estado de Nascimento (UF)",
        help_text="Sigla do estado (ex: SP, MG, TO). Usado para as Origens Regionais."
    )

    def __str__(self):
        return self.nome

    def get_age(self):
        if self.data_nascimento:
            today = date.today()
            if self.data_falecimento:
                age_date = self.data_falecimento
            elif self.data_falecimento_incerta:
                return "N/A (Falecido)"
            else:
                age_date = today

            age = age_date.year - self.data_nascimento.year - \
                  ((age_date.month, age_date.day) < (self.data_nascimento.month, self.data_nascimento.day))
            return age
        return None

    def is_deceased(self):
        return self.data_falecimento is not None or bool(self.data_falecimento_incerta)

    def get_status_vida_display(self):
        if self.is_deceased():
            if self.data_falecimento:
                return "Falecido(a)"
            elif self.data_falecimento_incerta:
                return f"Falecido(a) ({self.data_falecimento_incerta})"
        return "Vivo(a)"

    def get_default_photo_url(self):
        return staticfiles_storage.url('pessoas/img/sem-foto.jpg')

    def get_relationship_to_user(self, user_pessoa):
        if not isinstance(user_pessoa, Pessoa):
            return "Pessoa na Árvore (Referência Inválida)"

        if self == user_pessoa:
            return "Você"

        # --- Relações Diretas (Pai, Mãe, Filho, Filha) ---
        if self.pk == user_pessoa.pai_id:
            return "Pai"
        if self.pk == user_pessoa.mae_id:
            return "Mãe"

        if self.pai == user_pessoa:
            return "Filho" if self.genero == 'M' else "Filha"
        if self.mae == user_pessoa:
            return "Filho" if self.genero == 'M' else "Filha"

        # --- Relações de Avós e Netos ---
        if user_pessoa.pai:
            if self.pk == user_pessoa.pai.pai_id:
                return "Avô Paterno"
            if self.pk == user_pessoa.pai.mae_id:
                return "Avó Paterna"
        if user_pessoa.mae:
            if self.pk == user_pessoa.mae.pai_id:
                return "Avô Materno"
            if self.pk == user_pessoa.mae.mae_id:
                return "Avó Materna"

        user_children = user_pessoa.filhos_do_pai.all() | user_pessoa.filhos_da_mae.all()
        for child in user_children.distinct():
            if self.pai == child or self.mae == child:
                return "Neto" if self.genero == 'M' else "Neta"

        # --- Relações de Bisavós e Bisnetos ---
        if user_pessoa.pai:
            if user_pessoa.pai.pai:
                if self.pk == user_pessoa.pai.pai.pai_id:
                    return "Bisavô Paterno-Paterno"
                if self.pk == user_pessoa.pai.pai.mae_id:
                    return "Bisavó Paterna-Paterna"
            if user_pessoa.pai.mae:
                if self.pk == user_pessoa.pai.mae.pai_id:
                    return "Bisavô Paterno-Materno"
                if self.pk == user_pessoa.pai.mae.mae_id:
                    return "Bisavó Paterna-Materna"

        if user_pessoa.mae:
            if user_pessoa.mae.pai:
                if self.pk == user_pessoa.mae.pai.pai_id:
                    return "Bisavô Materno-Paterno"
                if self.pk == user_pessoa.mae.pai.mae_id:
                    return "Bisavó Materna-Paterna"
            if user_pessoa.mae.mae:
                if self.pk == user_pessoa.mae.mae.pai_id:
                    return "Bisavô Materno-Materno"
                if self.pk == user_pessoa.mae.mae.mae_id:
                    return "Bisavó Materna-Materna"

        ancestors_of_user = user_pessoa._get_ancestors_with_levels()
        descendants_of_user = user_pessoa._get_descendants_with_levels()

        if self.pk in ancestors_of_user and ancestors_of_user[self.pk] == 3:
            return "Bisavô" if self.genero == 'M' else "Bisavó"

        if self.pk in descendants_of_user and descendants_of_user[self.pk] == 3:
            return "Bisneto" if self.genero == 'M' else "Bisneta"


        # --- Relações de Irmãos e Meios-irmãos ---
        common_father = (self.pai and user_pessoa.pai and self.pai == user_pessoa.pai)
        common_mother = (self.mae and user_pessoa.mae and self.mae == user_pessoa.mae)

        if common_father and common_mother:
            return "Irmão Completo" if self.genero == 'M' else "Irmã Completa"
        elif common_father or common_mother:
            return "Meio-irmão" if self.genero == 'M' else "Meia-irmã"

        # --- Relações de Tios e Sobrinhos ---
        if user_pessoa.pai:
            if user_pessoa.pai.pai and self.pk in [s.pk for s in user_pessoa.pai.pai.filhos_do_pai.all() if s.pk != user_pessoa.pai.pk]:
                 return "Tio Paterno" if self.genero == 'M' else "Tia Paterna"
            if user_pessoa.pai.mae and self.pk in [s.pk for s in user_pessoa.pai.mae.filhos_da_mae.all() if s.pk != user_pessoa.pai.pk]:
                 return "Tio Paterno" if self.genero == 'M' else "Tia Paterna"

        if user_pessoa.mae:
            if user_pessoa.mae.pai and self.pk in [s.pk for s in user_pessoa.mae.pai.filhos_do_pai.all() if s.pk != user_pessoa.mae.pk]:
                 return "Tio Materno" if self.genero == 'M' else "Tia Materna"
            if user_pessoa.mae.mae and self.pk in [s.pk for s in user_pessoa.mae.mae.filhos_da_mae.all() if s.pk != user_pessoa.mae.pk]:
                 return "Tio Materno" if self.genero == 'M' else "Tia Materna"

        brothers_sisters_of_user = user_pessoa._get_siblings()
        for sibling in brothers_sisters_of_user:
            if self.pai == sibling or self.mae == sibling:
                return "Sobrinho" if self.genero == 'M' else "Sobrinha"

        # --- Primos de Primeiro Grau ---
        self_ancestor_ids = set(self._get_ancestors_with_levels().keys())
        user_ancestor_ids = set(user_pessoa._get_ancestors_with_levels().keys())

        common_ancestors_ids = self_ancestor_ids.intersection(user_ancestor_ids)

        if common_ancestors_ids:
            for ancestor_pk in common_ancestors_ids:
                if self._get_ancestors_with_levels().get(ancestor_pk) == 2 and \
                   user_pessoa._get_ancestors_with_levels().get(ancestor_pk) == 2:

                    if (self.pai and user_pessoa.pai and self.pai._get_siblings().filter(pk=user_pessoa.pai.pk).exists()) or \
                       (self.mae and user_pessoa.mae and self.mae._get_siblings().filter(pk=user_pessoa.mae.pk).exists()) or \
                       (self.pai and user_pessoa.mae and self.pai._get_siblings().filter(pk=user_pessoa.mae.pk).exists()) or \
                       (self.mae and user_pessoa.pai and self.mae._get_siblings().filter(pk=user_pessoa.pai.pk).exists()):
                        return "Primo(a) de Primeiro Grau"

        return "Parentesco Indefinido"

    # --- Métodos Auxiliares para Traversal da Árvore ---

    def _get_ancestors_with_levels(self):
        """ Retorna um dicionário de {Pessoa.pk: level} para todos os ancestrais. """
        ancestors = {}
        queue = deque([(self, 0)])
        visited = {self.pk}

        while queue:
            current_person, level = queue.popleft()

            if current_person.pai and current_person.pai.pk not in visited:
                ancestors[current_person.pai.pk] = level + 1
                visited.add(current_person.pai.pk)
                queue.append((current_person.pai, level + 1))

            if current_person.mae and current_person.mae.pk not in visited:
                ancestors[current_person.mae.pk] = level + 1
                visited.add(current_person.mae.pk)
                queue.append((current_person.mae, level + 1))
        return ancestors

    def _get_descendants_with_levels(self):
        """ Retorna um dicionário de {Pessoa.pk: level} para todos os descendentes. """
        descendants = {}
        queue = deque([(self, 0)])
        visited = {self.pk}

        while queue:
            current_person, level = queue.popleft()

            children = current_person.filhos_do_pai.all() | current_person.filhos_da_mae.all()

            for child in children.distinct():
                if child.pk not in visited:
                    descendants[child.pk] = level + 1
                    visited.add(child.pk)
                    queue.append((child, level + 1))
        return descendants

    def _get_siblings(self):
        """ Retorna um QuerySet de todos os irmãos (completos e meios) desta pessoa. """
        siblings = Pessoa.objects.none()

        if self.pai:
            siblings = siblings | self.pai.filhos_do_pai.all()
        if self.mae:
            siblings = siblings | self.mae.filhos_da_mae.all()

        return siblings.exclude(pk=self.pk).distinct()