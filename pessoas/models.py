# satilo/pessoas/models.py

from django.db import models
from datetime import date
from collections import deque
from django.contrib.staticfiles.storage import staticfiles_storage
from django.contrib.auth.models import User

class Pessoa(models.Model):
    # --- CAMPOS OBRIGATÓRIOS ---
    nome = models.CharField(max_length=200, verbose_name="Nome Completo") # Aumentei o max_length para nomes maiores
    genero = models.CharField(
        max_length=1, 
        choices=[('M', 'Masculino'), ('F', 'Feminino'), ('O', 'Outro')], # Adicionado 'Outro' para mais inclusão
        verbose_name="Gênero"
    )

    # --- CAMPOS OPCIONAIS (null=True, blank=True) ---
    data_nascimento = models.DateField(null=True, blank=True, verbose_name="Data de Nascimento")
    local_nascimento = models.CharField(max_length=200, blank=True, null=True, verbose_name="Local de Nascimento")
    estado_nascimento = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        verbose_name="Estado de Nascimento (UF)",
        help_text="Sigla do estado (ex: SP, MG, TO). Usado para as Origens Regionais."
    )
    
    data_falecimento = models.DateField(null=True, blank=True, verbose_name="Data de Falecimento")
    data_falecimento_incerta = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Data de Falecimento (Incerta)",
        help_text="Ex: 'cerca de 1950', 'antes de 1990', 'final do século XX'. Preenche se a data exata for desconhecida."
    )
    
    pai = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        related_name='filhos_do_pai', 
        on_delete=models.SET_NULL,
        verbose_name="Pai"
    )
    mae = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        related_name='filhos_da_mae', 
        on_delete=models.SET_NULL,
        verbose_name="Mãe"
    )
    
    # Mantendo ForeignKey para cônjuge, como estava no seu código. 
    # Isso permite que uma pessoa seja "cônjuge" de várias outras, se você gerenciar isso na lógica.
    # Se for para ser um único cônjuge atual, use OneToOneField, mas aí o `related_name` seria `conjuge_de`.
    conjuge = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conjuges_historicos', # Nome mais descritivo se for para múltiplos cônjuges
        verbose_name="Cônjuge Principal" # Ou "Cônjuge Atual" se for OneToOne
    )

    # REMOVIDO: o campo 'user'. O campo 'owner' já serve para ligar a pessoa ao usuário logado.
    # owner é crucial e deve ser obrigatório para a sua lógica de isolamento de dados por usuário.
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE, # Se o usuário for excluído, todas as suas pessoas são excluídas
        related_name='pessoas_proprietarias',
        verbose_name="Proprietário",
        help_text="O usuário que gerencia/criou esta pessoa na árvore."
    )

    foto = models.ImageField(upload_to='fotos_pessoas/', null=True, blank=True, verbose_name="Foto")
    historia_pessoal = models.TextField(null=True, blank=True, verbose_name="História Pessoal")
    
    # O campo 'relacao' é calculado dinamicamente nas views e não deve ser um campo de modelo.
    # Ele foi removido para evitar redundância e complexidade desnecessária no banco de dados.
    # Sua lógica de cálculo em `get_relationship_to_user` já está nas views.
    # Se você *precisa* armazenar a "relação principal" *definida pelo usuário*, aí sim seria um campo.
    # Pelo contexto, ele parece ser uma propriedade calculada.
    # Se você quiser que o usuário *escolha* uma relação, então ele deve ser um campo de formulário e de modelo.
    # Deixarei ele de fora do modelo por agora, para simplificar.
    # Se o objetivo é que o usuário defina uma relação manual, me avise.

    class Meta:
        verbose_name = "Pessoa"
        verbose_name_plural = "Pessoas"
        ordering = ['nome'] # Manter a ordenação

    def __str__(self):
        return self.nome

    # --- Métodos de Propriedade e Utilitários (mantidos e ligeiramente ajustados) ---
    def get_age(self):
        if not self.data_nascimento:
            return "N/A"
        
        today = date.today()
        birth_date = self.data_nascimento

        if self.data_falecimento:
            end_date = self.data_falecimento
        elif self.data_falecimento_incerta: # Retorna N/A se a data exata de falecimento é incerta
            return "N/A (Falecido)"
        else:
            end_date = today

        age = end_date.year - birth_date.year
        if end_date.month < birth_date.month or (end_date.month == birth_date.month and end_date.day < birth_date.day):
            age -= 1
        
        return age if age >= 0 else 0 # Garante que a idade não seja negativa

    def is_deceased(self):
        return self.data_falecimento is not None or bool(self.data_falecimento_incerta)

    def get_status_vida_display(self):
        if self.is_deceased():
            if self.data_falecimento:
                return "Falecido(a)"
            elif self.data_falecimento_incerta:
                return f"Falecido(a) ({self.data_falecimento_incerta})"
        return "Vivo(a)"

    @property
    def foto_url(self):
        if self.foto and hasattr(self.foto, 'url'):
            return self.foto.url
        return staticfiles_storage.url('pessoas/img/sem-foto.jpg')

    # --- Métodos de Parentesco (simplificados para o escopo do modelo) ---
    # Removi a lógica complexa de BFS e a maioria das checagens de owner/superuser daqui
    # Pois essa lógica deve ser mais apropriadamente tratada nas views ou em um manager
    # para garantir que as buscas de parentesco respeitem as permissões do usuário logado.
    # O modelo deve focar na estrutura dos dados, não nos filtros de permissão de visualização.

    def _get_ancestors_with_levels(self):
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
        descendants = {}
        queue = deque([(self, 0)])
        visited = {self.pk}

        while queue:
            current_person, level = queue.popleft()

            # Aqui você pode precisar otimizar o acesso ao DB.
            # `filhos_do_pai` e `filhos_da_mae` são `related_name` que o Django cria
            # automaticamente para o ManyToOneField reverso.
            children = current_person.filhos_do_pai.all() | current_person.filhos_da_mae.all()

            for child in children.distinct():
                if child.pk not in visited:
                    descendants[child.pk] = level + 1
                    visited.add(child.pk)
                    queue.append((child, level + 1))
        return descendants

    def _get_siblings(self):
        siblings = Pessoa.objects.none()

        if self.pai:
            siblings = siblings | self.pai.filhos_do_pai.all()
        if self.mae:
            siblings = siblings | self.mae.filhos_da_mae.all()

        return siblings.exclude(pk=self.pk).distinct()

    def _get_spouses(self):
        spouses = []
        if self.conjuge:
            spouses.append(self.conjuge)
        # Se você permitir múltiplos cônjuges através de um campo ManyToMany ou modelo intermediário
        # esta lógica precisaria ser expandida. Com um ForeignKey simples como conjuge,
        # self.conjuge é o "único" cônjuge direto registrado para essa pessoa.
        # Para cônjuges REVERSOS (outras pessoas que apontam para 'self' como cônjuge),
        # você teria que usar self.conjuges_historicos.all() se 'conjuges_historicos'
        # for o related_name reverso, ou então Pessoa.objects.filter(conjuge=self).
        
        # Considerando a `related_name='conjuges_historicos'` definida acima para `conjuge`:
        for spouse_reverse in self.conjuges_historicos.all(): # Isso pega pessoas que têm esta pessoa como seu `conjuge`
            if spouse_reverse not in spouses: # Evita duplicatas se self.conjuge também aponta para self.
                spouses.append(spouse_reverse)

        return spouses
    
    @staticmethod
    def _get_common_ancestor_info_for_two_persons(person1, person2):
        if not isinstance(person1, Pessoa) or not isinstance(person2, Pessoa):
            return {}

        ancestors1 = person1._get_ancestors_with_levels()
        ancestors2 = person2._get_ancestors_with_levels()

        common_ancestors_info = {}
        for anc_pk, level1 in ancestors1.items():
            if anc_pk in ancestors2:
                common_ancestors_info[anc_pk] = {'level1': level1, 'level2': ancestors2[anc_pk]}
        return common_ancestors_info

    # Esta função de parentesco será mais robusta se for chamada com os dados JÁ FILTRADOS
    # pelo owner. Assim, ela não precisa fazer filtros de owner internamente.
    def get_relationship_to_user(self, user_pessoa):
        if not isinstance(user_pessoa, Pessoa):
            return "Referência Inválida"

        if self.pk == user_pessoa.pk:
            return "Você"

        # Calcular todos os ancestrais/descendentes uma vez para cada pessoa
        # O filtro de owner DEVE ser feito antes de construir esses mapas
        # nas views (_populate_all_tree_data) para evitar travessia em árvores de outros usuários.
        ancestors_of_self = self._get_ancestors_with_levels()
        ancestors_of_user = user_pessoa._get_ancestors_with_levels()
        descendants_of_self = self._get_descendants_with_levels()
        descendants_of_user = user_pessoa._get_descendants_with_levels()

        # Prioridades para relações diretas
        if self.pk == user_pessoa.pai_id: return "Pai"
        if self.pk == user_pessoa.mae_id: return "Mãe"
        
        if self.pai_id == user_pessoa.pk or self.mae_id == user_pessoa.pk:
            return "Filho(a)" # Retorna genérico para filho(a)

        # Cônjuge
        # Verifica se 'self' é o conjuge da user_pessoa OU se user_pessoa é conjuge de 'self'
        if self.conjuge and self.conjuge.pk == user_pessoa.pk:
            return "Cônjuge"
        # Verifica cônjuges reversos (pessoas que têm user_pessoa como cônjuge)
        for reverse_spouse in user_pessoa.conjuges_historicos.all():
            if self.pk == reverse_spouse.pk:
                return "Cônjuge"

        # Irmão(ã)
        common_parents = 0
        if self.pai_id and user_pessoa.pai_id and self.pai_id == user_pessoa.pai_id:
            common_parents += 1
        if self.mae_id and user_pessoa.mae_id and self.mae_id == user_pessoa.mae_id:
            common_parents += 1
        
        if common_parents == 2:
            return "Irmão(ã) Completo(a)"
        elif common_parents == 1:
            return "Meio-irmão(ã)"

        # Avós / Netos
        if self.pk in ancestors_of_user and ancestors_of_user[self.pk] == 2:
            return "Avô(ó)"
        if self.pk in descendants_of_user and descendants_of_user[self.pk] == 2:
            return "Neto(a)"

        # Bisavós / Bisnetos
        if self.pk in ancestors_of_user and ancestors_of_user[self.pk] == 3:
            return "Bisavô(ó)"
        if self.pk in descendants_of_user and descendants_of_user[self.pk] == 3:
            return "Bisneto(a)"
            
        # Tataravós / Tatarane(ta/to)
        if self.pk in ancestors_of_user and ancestors_of_user[self.pk] == 4:
            return "Tataravô(ó)"
        if self.pk in descendants_of_user and descendants_of_user[self.pk] == 4:
            return "Tatarane(ta/to)"
            
        # Tios / Sobrinhos
        user_parents_pks = set()
        if user_pessoa.pai_id: user_parents_pks.add(user_pessoa.pai_id)
        if user_pessoa.mae_id: user_parents_pks.add(user_pessoa.mae_id)

        for parent_pk in user_parents_pks:
            try:
                parent_obj = Pessoa.objects.get(pk=parent_pk)
                if self.pk in parent_obj._get_siblings().values_list('pk', flat=True):
                    return "Tio(a)"
            except Pessoa.DoesNotExist:
                pass # Não faz nada se o pai/mãe não for encontrado (pode ter sido filtrado por owner)

        user_siblings = user_pessoa._get_siblings()
        user_siblings_pks = user_siblings.values_list('pk', flat=True)
        if self.pai_id and self.pai_id in user_siblings_pks:
            return "Sobrinho(a)"
        if self.mae_id and self.mae_id in user_siblings_pks:
            return "Sobrinho(a)"

        # Tio(a)-Avô(ó) / Sobrinho(a)-Neto(a)
        user_grandparents_pks = set()
        for anc_pk, level in ancestors_of_user.items():
            if level == 2: # Avós
                user_grandparents_pks.add(anc_pk)
        
        for gp_pk in user_grandparents_pks:
            try:
                gp_obj = Pessoa.objects.get(pk=gp_pk)
                if self.pk in gp_obj._get_siblings().values_list('pk', flat=True):
                    return "Tio(a)-Avô(ó)"
            except Pessoa.DoesNotExist:
                pass

        for sibling in user_siblings:
            descendants_of_sibling = sibling._get_descendants_with_levels()
            if self.pk in descendants_of_sibling and descendants_of_sibling[self.pk] == 2:
                return "Sobrinho(a)-Neto(a)"

        # Primos
        # 1. Primo(a) de Primeiro Grau: têm avós em comum.
        #    Ou, mais diretamente: filhos de irmãos dos seus pais.
        for anc_pk, level_to_ancestor_self in ancestors_of_self.items():
            if anc_pk in ancestors_of_user:
                level_to_ancestor_user = ancestors_of_user[anc_pk]
                # Se ambos estão a 2 gerações do ancestral comum (avós)
                if level_to_ancestor_self == 2 and level_to_ancestor_user == 2:
                    return "Primo(a) de Primeiro Grau"
        
        # Genro/Nora (cônjuge de um filho(a) da user_pessoa)
        user_children = user_pessoa.filhos_do_pai.all() | user_pessoa.filhos_da_mae.all()
        for child in user_children.distinct():
            if child.conjuge and self.pk == child.conjuge.pk:
                return "Genro" if self.genero == 'M' else "Nora"

        # Sogro/Sogra (pai/mãe do cônjuge da user_pessoa)
        if user_pessoa.conjuge:
            if self.pk == user_pessoa.conjuge.pai_id or self.pk == user_pessoa.conjuge.mae_id:
                return "Sogro" if self.genero == 'M' else "Sogra"

        # Cunhado(a) (cônjuge de um irmão/irmã da user_pessoa, ou irmão/irmã do cônjuge da user_pessoa)
        for sibling in user_siblings:
            if sibling.conjuge and self.pk == sibling.conjuge.pk:
                return "Cunhado(a)"
        
        if user_pessoa.conjuge:
            user_spouse_siblings = user_pessoa.conjuge._get_siblings()
            user_spouse_siblings_pks = user_spouse_siblings.values_list('pk', flat=True)
            if self.pk in user_spouse_siblings_pks:
                return "Cunhado(a)"

        # Padrasto/Madrasta / Enteado(a)
        # Se 'self' é cônjuge de um dos pais da user_pessoa
        if user_pessoa.pai and self.pk == user_pessoa.pai.conjuge_id:
            return "Madrasta" if self.genero == 'F' else "Padrasto"
        if user_pessoa.mae and self.pk == user_pessoa.mae.conjuge_id:
            return "Padrasto" if self.genero == 'M' else "Madrasta"

        # Se 'self' é filho(a) do cônjuge da user_pessoa (e não é filho(a) biológico)
        if user_pessoa.conjuge:
            if self.pai_id == user_pessoa.conjuge.pk or self.mae_id == user_pessoa.conjuge.pk:
                # Precisa ser um enteado, ou seja, não ser filho(a) da user_pessoa também
                if not (self.pai_id == user_pessoa.pk or self.mae_id == user_pessoa.pk):
                    return "Enteado(a)"
        
        # --- Novas Regras de Parentesco ---

        # Tia por Afinidade (cônjuge do tio/tia)
        # Um tio(a) é um(a) irmão(ã) de um dos pais do user_pessoa.
        # Se 'self' é cônjuge de um tio/tia do user_pessoa.
        for parent_pk in user_parents_pks:
            try:
                parent_obj = Pessoa.objects.get(pk=parent_pk)
                for sibling_of_parent in parent_obj._get_siblings():
                    if sibling_of_parent.conjuge and self.pk == sibling_of_parent.conjuge.pk:
                        return "Tia por Afinidade" if self.genero == 'F' else "Tio por Afinidade"
            except Pessoa.DoesNotExist:
                pass
        
        # Primo(a) de Segundo Grau
        # Sua mãe/pai é primo(a) de primeiro grau da pessoa.
        # Ou seja, vocês têm bisavós em comum (3 gerações de distância para o ancestral comum)
        for anc_pk, level_to_ancestor_self in ancestors_of_self.items():
            if anc_pk in ancestors_of_user:
                level_to_ancestor_user = ancestors_of_user[anc_pk]
                # Se um está a 2 gerações e o outro a 3 gerações, ou ambos a 3 gerações do ancestral comum
                # Isso cobre o caso em que o ancestral comum é um bisavô para ambos.
                # Ou quando um é neto de um irmão do avô do outro.
                # A lógica mais simples para "primo de segundo grau" é "filho de primo de primeiro grau"
                # ou "vocês têm um bisavô em comum".
                
                # Para simplificar: se o ancestral comum é 3 níveis acima para ambos
                if level_to_ancestor_self == 3 and level_to_ancestor_user == 3:
                    return "Primo(a) de Segundo Grau"
                
                # Lógica para "filho de primo de primeiro grau":
                # Verificamos se 'self' é filho de alguém que é primo de primeiro grau do 'user_pessoa'.
                # Isso seria mais complexo de verificar diretamente no _get_relationship_to_user,
                # pois requer verificar a relação de 'self.pai' ou 'self.mae' com 'user_pessoa'.
                # Uma abordagem mais robusta para primos de N-grau é:
                # Encontrar o ancestral comum mais próximo e somar as distâncias de ambos a ele,
                # e subtrair 2 (pois os pais seriam o "grau 0" de parentesco colateral).
                
                # Calculando o grau do primo: min(level1, level2) - 1. Se ambos são 2, 2-1 = primo de 1º.
                # Se um é 2 e outro 3 (por exemplo, filho de um primo de 1º), min(2,3)-1 = 1, ainda primo de 1º.
                # Para ser primo de segundo grau, a distância mínima até o ancestral comum (o avô do avô ou o bisavô)
                # deveria ser 3.
                
                # Se o ancestral comum for um bisavô (level 3 para ambos)
                if level_to_ancestor_self >= 3 and level_to_ancestor_user >= 3:
                    # O grau de parentesco colateral é a soma das distâncias até o ancestral comum, menos 2.
                    # Ex: self (2) -> avô_comum (0) <- (2) user_pessoa => 2+2-2 = 2 (primo de 1º)
                    # Ex: self (3) -> bisavô_comum (0) <- (3) user_pessoa => 3+3-2 = 4 (primo de 2º)
                    # O "grau" de primo é dado por min(distancia_self_anc_comum, distancia_user_anc_comum) - 1.
                    
                    min_level = min(level_to_ancestor_self, level_to_ancestor_user)
                    if min_level == 3:
                        return "Primo(a) de Segundo Grau"
                    elif min_level == 4:
                        return "Primo(a) de Terceiro Grau" # Adicionando para o futuro, se quiser
        
        return "Parentesco Indefinido" # Fallback se nenhuma regra se aplica