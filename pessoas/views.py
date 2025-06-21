# pessoas/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from .models import Pessoa
from datetime import date
from collections import deque
from django.contrib.auth import login
from .forms import PessoaForm, UserRegistrationForm
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

# Variáveis globais para o contexto da árvore (voltando ao estado original para views HTML)
_global_nodes_map = {}
_global_families_map = {}
_user_ref_for_rel = None
_pessoa_raiz_global = None

# Mapeamento de UF para Região
UF_TO_REGIAO = {
    'AC': 'Norte', 'AM': 'Norte', 'AP': 'Norte', 'PA': 'Norte', 'RO': 'Norte', 'RR': 'Norte', 'TO': 'Norte',
    'AL': 'Nordeste', 'BA': 'Nordeste', 'CE': 'Nordeste', 'MA': 'Nordeste', 'PB': 'Nordeste',
    'PE': 'Nordeste', 'PI': 'Piauí', 'RN': 'Nordeste', 'SE': 'Nordeste',
    'DF': 'Centro-Oeste', 'GO': 'Centro-Oeste', 'MS': 'Centro-Oeste', 'MT': 'Centro-Oeste',
    'ES': 'Sudeste', 'MG': 'Sudeste', 'SP': 'Sudeste',
    'RJ': 'Sudeste',
    'PR': 'Sul', 'RS': 'Sul', 'SC': 'Sul',
}

# Modificada para aceitar o usuário atual para filtragem
def _get_person_data(person_obj, current_user_filter):
    """
    Retorna os dados formatados de uma pessoa e os armazena no mapa global de nós.
    A pessoa só é adicionada ao mapa se pertencer ao current_user_filter ou se o user for superuser.
    """
    global _global_nodes_map, _user_ref_for_rel, _pessoa_raiz_global

    if not person_obj:
        return None
    if not hasattr(person_obj, 'pk'):
        return None

    # FILTRO POR OWNER AQUI (Lógica original e funcional)
    if person_obj.owner and person_obj.owner.pk != current_user_filter.pk and not current_user_filter.is_superuser:
        print(f"DEBUG: _get_person_data: Filtering out {person_obj.nome} (ID: {person_obj.pk}) - different owner or not superuser.")
        return None

    if person_obj.pk in _global_nodes_map:
        return _global_nodes_map[person_obj.pk]

    data = {
        'id': person_obj.pk,
        'nome': person_obj.nome,
        'foto_url': person_obj.foto_url,
        'data_nascimento': str(person_obj.data_nascimento) if person_obj.data_nascimento else None,
        'data_falecimento': str(person_obj.data_falecimento) if person_obj.data_falecimento else None,
        'data_falecimento_incerta': person_obj.data_falecimento_incerta,
        'genero': person_obj.genero,
        'relacao': person_obj.get_relationship_to_user(_user_ref_for_rel),
        'idade': person_obj.get_age(),
        'status_vida': person_obj.get_status_vida_display(),
        'type': 'person',
        'is_root_display_node': (person_obj.pk == (_pessoa_raiz_global.pk if _pessoa_raiz_global else None)),
        'is_user_selected': (person_obj.pk == (_user_ref_for_rel.pk if _user_ref_for_rel else None)),
        'historia_pessoal': person_obj.historia_pessoal,
        'local_nascimento': person_obj.local_nascimento,
        'estado_nascimento': person_obj.estado_nascimento,
        'pai_id': person_obj.pai.pk if person_obj.pai else None,
        'mae_id': person_obj.mae.pk if person_obj.mae else None,
        'owner_id': person_obj.owner.pk if person_obj.owner else None,
    }
    _global_nodes_map[person_obj.pk] = data
    print(f"DEBUG: _get_person_data: Added {person_obj.nome} (ID: {person_obj.pk}) to _global_nodes_map. Owner: {person_obj.owner.username if person_obj.owner else 'N/A'}")
    return data

# Modificada para aceitar o usuário atual para filtragem de filhos e cônjuges
def _add_family_unit_to_global_map(husband_obj, wife_obj, current_user_filter):
    """
    Cria ou recupera uma unidade familiar (casal).
    As pessoas na unidade familiar e seus filhos devem pertencer ao current_user_filter
    ou ser superuser vendo a árvore de qualquer um, para serem processados.
    """
    global _global_families_map, _global_nodes_map

    # Filtra marido e esposa pelo owner - se nenhum dos dois for válido, a unidade familiar não é relevante
    husband_is_valid = husband_obj and (husband_obj.owner == current_user_filter or current_user_filter.is_superuser)
    wife_is_valid = wife_obj and (wife_obj.owner == current_user_filter or current_user_filter.is_superuser)

    if not husband_is_valid and not wife_is_valid:
        return None

    husband_pk = str(husband_obj.pk) if husband_obj else 'none'
    wife_pk = str(wife_obj.pk) if wife_obj else 'none'
    family_id = f"family_{husband_pk}_{wife_pk}"

    if family_id in _global_families_map:
        return _global_families_map[family_id]

    family_data = {
        'id': family_id,
        'type': 'family_unit',
        'husband_id': husband_obj.pk if husband_obj else None,
        'wife_id': wife_obj.pk if wife_obj else None,
        'children_ids': [], # IDs dos PKs das pessoas que são filhas diretas deste casal
    }
    _global_families_map[family_id] = family_data

    # Passa os objetos originais, o filtro é feito dentro de _get_person_data
    _get_person_data(husband_obj, current_user_filter)
    _get_person_data(wife_obj, current_user_filter)

    # Adiciona os filhos a esta unidade familiar, filtrando-os estritamente por owner
    children_qs = Pessoa.objects.none()

    # APENAS filhos que pertencem ao usuário logado ou superuser são considerados.
    base_children_query = Pessoa.objects.filter(owner=current_user_filter)
    if current_user_filter.is_superuser:
        base_children_query = Pessoa.objects.all() # Superuser pode ver todos os filhos cadastrados

    if husband_obj and wife_obj:
        children_qs = base_children_query.filter(pai=husband_obj, mae=wife_obj)
    elif husband_obj:
        children_qs = base_children_query.filter(pai=husband_obj, mae__isnull=True)
    elif wife_obj:
        children_qs = base_children_query.filter(mae=wife_obj, pai__isnull=True)

    for child_obj in children_qs.distinct().order_by('data_nascimento'):
        family_data['children_ids'].append(child_obj.pk)
        _get_person_data(child_obj, current_user_filter) # Garante que o filho esteja no global_nodes_map

    return family_data

# Modificada para aceitar o usuário atual para filtragem de toda a árvore
def _populate_all_tree_data(start_person_obj_orm, current_user_filter):
    """
    Popula os mapas globais de nós (Pessoas) e famílias (Casais) navegando pela árvore.
    Esta função filtra todas as pessoas pela propriedade 'owner' DURANTE a travessia,
    para manter a isolação por usuário.
    """
    global _global_nodes_map, _global_families_map, _user_ref_for_rel, _pessoa_raiz_global
    _global_nodes_map = {} # Reinicia os mapas globais para cada requisição de árvore
    _global_families_map = {}

    if not start_person_obj_orm:
        print("DEBUG: _populate_all_tree_data: start_person_obj_orm is None.")
        return

    # O filtro de owner para a pessoa raiz é feito ANTES de chamar _populate_all_tree_data na arvore_genealogica.
    # Se a pessoa_raiz não pertence ao usuário e não é superuser, a função arvore_genealogica já deve ter retornado.
    _get_person_data(start_person_obj_orm, current_user_filter)

    queue_persons = deque([start_person_obj_orm])
    visited_persons_pks = {start_person_obj_orm.pk}
    visited_family_ids = set() # Para evitar reprocessar a mesma unidade familiar

    print(f"\nDEBUG: --- Starting BFS from {start_person_obj_orm.nome} (ID: {start_person_obj_orm.pk}), User: {current_user_filter.username} (Is Superuser: {current_user_filter.is_superuser}) ---")

    while queue_persons:
        current_person_obj = queue_persons.popleft()
        print(f"DEBUG: Processing {current_person_obj.nome} (ID: {current_person_obj.pk}). Queue size: {len(queue_persons)}")

        # 1. Processar pais da pessoa atual, filtrando por owner
        pai_obj = current_person_obj.pai
        mae_obj = current_person_obj.mae

        parent_family = _add_family_unit_to_global_map(pai_obj, mae_obj, current_user_filter)
        if parent_family and parent_family['id'] not in visited_family_ids:
            visited_family_ids.add(parent_family['id'])

            # Adiciona os pais à fila APENAS se já estiverem no _global_nodes_map (ou seja, passaram pelo filtro de owner em _get_person_data)
            if pai_obj and pai_obj.pk not in visited_persons_pks and pai_obj.pk in _global_nodes_map:
                queue_persons.append(pai_obj)
                visited_persons_pks.add(pai_obj.pk)
                print(f"DEBUG: Added parent {pai_obj.nome} (ID: {pai_obj.pk}) to queue.")
            elif pai_obj and pai_obj.pk not in _global_nodes_map:
                print(f"DEBUG: Parent {pai_obj.nome} (ID: {pai_obj.pk}) not in _global_nodes_map (owner mismatch), skipped for queue.")

            if mae_obj and mae_obj.pk not in visited_persons_pks and mae_obj.pk in _global_nodes_map:
                queue_persons.append(mae_obj)
                visited_persons_pks.add(mae_obj.pk)
                print(f"DEBUG: Added parent {mae_obj.nome} (ID: {mae_obj.pk}) to queue.")
            elif mae_obj and mae_obj.pk not in _global_nodes_map:
                print(f"DEBUG: Mother {mae_obj.nome} (ID: {mae_obj.pk}) not in _global_nodes_map (owner mismatch), skipped for queue.")

        # 2. Processar parceiros e filhos da pessoa atual, filtrando por owner
        spouses_of_current_person = set()

        # Cônjuge direto da pessoa atual
        if current_person_obj.conjuge:
            spouses_of_current_person.add(current_person_obj.conjuge)

        # Cônjuges reversos (quem tem current_person_obj como seu cônjuge)
        for spouse_of_current in Pessoa.objects.filter(conjuge=current_person_obj):
            spouses_of_current_person.add(spouse_of_current)

        # Remova None do conjunto, se existir
        if None in spouses_of_current_person:
            spouses_of_current_person.remove(None)

        for spouse_obj in spouses_of_current_person:
            husband_candidate = current_person_obj if current_person_obj.genero == 'M' else spouse_obj
            wife_candidate = current_person_obj if current_person_obj.genero == 'F' else spouse_obj

            # Cria a unidade familiar para este casal. O filtro de owner acontece DENTRO de _add_family_unit_to_global_map
            child_family_unit = _add_family_unit_to_global_map(husband_candidate, wife_candidate, current_user_filter)
            if child_family_unit and child_family_unit['id'] not in visited_family_ids:
                visited_family_ids.add(child_family_unit['id'])

                # Adiciona o parceiro à fila se já estiver no _global_nodes_map
                if spouse_obj and spouse_obj.pk not in visited_persons_pks and spouse_obj.pk in _global_nodes_map:
                    queue_persons.append(spouse_obj)
                    visited_persons_pks.add(spouse_obj.pk)
                    print(f"DEBUG: Added spouse {spouse_obj.nome} (ID: {spouse_obj.pk}) to queue (from processing {current_person_obj.nome}).")
                elif spouse_obj and spouse_obj.pk not in _global_nodes_map:
                    print(f"DEBUG: Spouse {spouse_obj.nome} (ID: {spouse_obj.pk}) not in _global_nodes_map (owner mismatch), skipped for queue.")

                # Adiciona os filhos deste casal à fila se já estiverem no _global_nodes_map
                for child_pk in child_family_unit['children_ids']:
                    if child_pk not in visited_persons_pks and child_pk in _global_nodes_map:
                        child_obj = Pessoa.objects.get(pk=child_pk)
                        queue_persons.append(child_obj)
                        visited_persons_pks.add(child_obj.pk)
                        print(f"DEBUG: Added child {child_obj.nome} (ID: {child_obj.pk}) from family unit to queue (from processing {current_person_obj.nome}).")
                    elif child_pk not in _global_nodes_map:
                        print(f"DEBUG: Child {child_pk} not in _global_nodes_map (owner mismatch), skipped for queue.")

        # NOVO BLOCO: Processar filhos da pessoa atual em relações de pai/mãe solteiro(a)
        # Isso garantirá que filhos com um pai/mãe nulo sejam encontrados
        single_parent_family = None
        if current_person_obj.genero == 'M': # Se for homem, pode ser pai solteiro
            single_parent_family = _add_family_unit_to_global_map(current_person_obj, None, current_user_filter)
        elif current_person_obj.genero == 'F': # Se for mulher, pode ser mãe solteira
            single_parent_family = _add_family_unit_to_global_map(None, current_person_obj, current_user_filter)

        if single_parent_family and single_parent_family['id'] not in visited_family_ids:
            visited_family_ids.add(single_parent_family['id'])
            for child_pk in single_parent_family['children_ids']:
                if child_pk not in visited_persons_pks and child_pk in _global_nodes_map: # Check if child in global nodes map
                    child_obj = Pessoa.objects.get(pk=child_pk)
                    queue_persons.append(child_obj)
                    visited_persons_pks.add(child_obj.pk)
                    print(f"DEBUG: Added single-parent child {child_obj.nome} (ID: {child_obj.pk}) to queue (from {current_person_obj.nome}).")
                elif child_pk not in _global_nodes_map:
                    print(f"DEBUG: Single-parent child {child_pk} not in _global_nodes_map (owner mismatch), skipped for queue.")

        # NOVO BLOCO: Adicionar irmãos à fila para travessia lateral a partir dos pais
        # Isso é crucial para encontrar tios, tias por afinidade e primos
        if current_person_obj.pai and current_person_obj.mae: # Se a pessoa tem ambos os pais
            # Obter a unidade familiar dos pais da pessoa atual
            parents_family_unit = _add_family_unit_to_global_map(current_person_obj.pai, current_person_obj.mae, current_user_filter)
            if parents_family_unit: # Se a família dos pais é válida para o owner
                for sibling_pk in parents_family_unit['children_ids']: # Iterar sobre todos os filhos desses pais (irmãos)
                    if sibling_pk != current_person_obj.pk and sibling_pk not in visited_persons_pks:
                        if sibling_pk in _global_nodes_map: # Se o irmão já está no mapa (pertence ao owner ou superuser)
                            sibling_obj = Pessoa.objects.get(pk=sibling_pk)
                            queue_persons.append(sibling_obj)
                            visited_persons_pks.add(sibling_obj.pk)
                            print(f"DEBUG: Added sibling {sibling_obj.nome} (ID: {sibling_obj.pk}) to queue (from shared parents of {current_person_obj.nome}).")
                        else:
                            print(f"DEBUG: Sibling {sibling_pk} not in _global_nodes_map (owner mismatch), skipped for queue.")

    print("DEBUG: --- BFS finished ---")


def home_page(request):
    return render(request, 'pessoas/home.html', {})

class ListaPessoas(ListView):
    model = Pessoa
    template_name = 'pessoas/lista_pessoas.html'
    context_object_name = 'pessoas'

    def get_queryset(self):
        # A lista de pessoas é filtrada pelo proprietário (owner)
        if self.request.user.is_authenticated:
            # Usuários logados só veem as pessoas que eles possuem (owner)
            return Pessoa.objects.filter(owner=self.request.user).order_by('nome')
        else:
            # Usuários não logados não veem nenhuma pessoa na lista.
            return Pessoa.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_pessoa = None
        if self.request.user.is_authenticated:
            # 1. Tenta obter a pessoa selecionada na sessão primeiro (a mais prioritária para 'você')
            user_selected_person_id = self.request.session.get('user_selected_person_id')
            if user_selected_person_id:
                try:
                    # AQUI: A pessoa da sessão deve ser válida OU o usuário superuser
                    if self.request.user.is_superuser:
                        user_pessoa = Pessoa.objects.get(pk=user_selected_person_id)
                    else:
                        user_pessoa = get_object_or_404(Pessoa, pk=user_selected_person_id, owner=self.request.user) # Garante que só pega o que pertence ao user
                except (Pessoa.DoesNotExist, AttributeError) as e:
                    # Captura tanto Pessoa.DoesNotExist quanto o erro de pessoa_associada
                    user_pessoa = None
                    if 'user_selected_person_id' in self.request.session: # Limpa a sessão se a pessoa não existe ou não é do owner
                        del self.request.session['user_selected_person_id']
                    print(f"DEBUG: Error retrieving user_pessoa from session (or it was invalid): {e}")

        # 2. Se a sessão não definiu 'user_pessoa', tenta a pessoa_associada (relacionamento OneToOne)
        if not user_pessoa:
            try:
                user_pessoa = self.request.user.pessoa_associada
            except (ObjectDoesNotExist, AttributeError) as e:
                user_pessoa = None
                # print(f"DEBUG: user.pessoa_associada not found or attribute error: {e}") # Comentado para não poluir log


        # 3. Se ainda não encontrou, tenta a primeira pessoa que o usuário possui
        if not user_pessoa:
            user_pessoa = Pessoa.objects.filter(owner=self.request.user).order_by('data_nascimento').first()
            # Opcional: Se encontrou uma primeira pessoa aqui e NADA estava na sessão,
            # pode considerar defini-la automaticamente na sessão para consistência futura.
            # if user_pessoa and not self.request.session.get('user_selected_person_id'):
            #       self.request.session['user_selected_person_id'] = user_pessoa.pk


        # Prepara a relação e o is_user_selected para cada pessoa na lista
        for pessoa in context['pessoas']:
            if user_pessoa:
                pessoa.relacao_com_principal = pessoa.get_relationship_to_user(user_pessoa)
                pessoa.is_user_selected = (pessoa.pk == user_pessoa.pk)
            else:
                pessoa.relacao_com_principal = "Pessoa na Árvore" # Relação genérica para não logados
                pessoa.is_user_selected = False # Ninguém selecionado se não logado

            pessoa.status_vida_display = pessoa.get_status_vida_display()
            pessoa.idade = pessoa.get_age()
            pessoa.local_nascimento = pessoa.local_nascimento
            pessoa.estado_nascimento = pessoa.estado_nascimento

        context['user_pessoa'] = user_pessoa # Adiciona user_pessoa ao contexto para o template
        return context

class CriaPessoa(CreateView):
    model = Pessoa
    template_name = 'pessoas/cria_pessoa.html'
    form_class = PessoaForm
    success_url = reverse_lazy('lista_pessoas')

    def form_valid(self, form):
        # MUITO IMPORTANTE: Atribuir o owner AQUI, antes de super().form_valid(form)
        if self.request.user.is_authenticated:
            form.instance.owner = self.request.user
            print(f"DEBUG VIEWS: form_valid - Owner definido como: {form.instance.owner.username}") # Para confirmar no terminal

            # Agora sim, chame o método form_valid da classe pai.
            # Neste ponto, form.instance.owner JÁ ESTÁ PREENCHIDO,
            # então a validação final do ModelForm (que o super().form_valid() faz)
            # não vai reclamar do campo 'owner' obrigatório.
            response = super().form_valid(form)

            # O restante da sua lógica após o salvamento
            newly_created_person = self.object
            self.request.session['user_selected_person_id'] = newly_created_person.pk
            messages.success(self.request, f"'{newly_created_person.nome}' foi adicionado(a) e definido(a) como a pessoa principal para visualização da árvore.")

            print(f"DEBUG VIEWS: form_valid - Pessoa salva com sucesso! ID: {newly_created_person.pk}")
            return response
        else:
            messages.error(self.request, "Você precisa estar logado para criar uma pessoa.")
            print("DEBUG VIEWS: form_valid - Usuário não autenticado, redirecionando para form_invalid.")
            return self.form_invalid(form)

    def form_invalid(self, form):
        print(f"DEBUG VIEWS: form_invalid - Formulário inválido detectado.")
        print(f"DEBUG VIEWS: Erros do formulário: {form.errors}")
        print(f"DEBUG VIEWS: Erros globais do formulário (non_field_errors): {form.non_field_errors}")
        return super().form_invalid(form)

    def post(self, request, *args, **kwargs):
        print("DEBUG VIEWS: Requisição POST recebida na CriaPessoa.")
        return super().post(request, *args, **kwargs)

# A EditaPessoa já deve estar OK, pois o owner já vem do objeto carregado.
# Certifique-se apenas que você tem o form.instance.owner = self.request.user na EditaPessoa
# APENAS se você quiser permitir que um superuser mude o owner, ou se o owner original não existir.
# Pelo que entendi, a EditaPessoa não precisa dessa atribuição, já que o owner é um campo do objeto existente.
class EditaPessoa(UpdateView):
    model = Pessoa
    template_name = 'pessoas/cria_pessoa.html'
    form_class = PessoaForm
    success_url = reverse_lazy('lista_pessoas')

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_authenticated and not self.request.user.is_superuser:
            return qs.filter(owner=self.request.user)
        return qs

    def form_valid(self, form):
        # Aqui, o form.instance já é a pessoa que está sendo editada e já tem um owner.
        # Não é necessário atribuir o owner novamente, a menos que você esteja mudando ele.
        print(f"DEBUG VIEWS: EditaPessoa - form_valid - Pessoa sendo editada: {form.instance.nome}")
        print(f"DEBUG VIEWS: EditaPessoa - Owner: {form.instance.owner.username}")
        response = super().form_valid(form)
        messages.success(self.request, f"'{form.instance.nome}' foi atualizado(a) com sucesso.")
        print(f"DEBUG VIEWS: EditaPessoa - Pessoa atualizada com sucesso! ID: {form.instance.pk}")
        return response

    def form_invalid(self, form):
        print(f"DEBUG VIEWS: EditaPessoa - Formulário inválido detectado.")
        print(f"DEBUG VIEWS: EditaPessoa - Erros do formulário: {form.errors}")
        print(f"DEBUG VIEWS: EditaPessoa - Erros globais do formulário (non_field_errors): {form.non_field_errors}")
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if not request.user.is_authenticated or \
           (obj.owner != request.user and not request.user.is_superuser):
            messages.error(request, "Você não tem permissão para editar esta pessoa.")
            return redirect('lista_pessoas')
        return super().dispatch(request, *args, **kwargs)


def set_user_person(request, person_id):
    try:
        person = get_object_or_404(Pessoa, pk=person_id)
        if request.user.is_authenticated:
            # Permite definir como 'você' apenas se a pessoa pertence ao usuário logado ou for superuser
            if person.owner == request.user or request.user.is_superuser:
                request.session['user_selected_person_id'] = person.pk
                messages.success(request, f"'{person.nome}' definido(a) como a pessoa principal para visualização da árvore.")
            else:
                messages.error(request, "Você não tem permissão para definir esta pessoa como sua raiz de visualização.")
        else: # Se não logado, não pode definir raiz da sessão
            messages.error(request, "Você precisa estar logado para definir sua pessoa raiz para visualização.")
    except Pessoa.DoesNotExist:
        messages.error(request, "Pessoa não encontrada para definir como a pessoa principal para visualização.")
    print(f"DEBUG: Redirecionando para lista_pessoas. Session ID after set: {request.session.get('user_selected_person_id')}")
    return redirect('lista_pessoas')


def arvore_genealogica(request, pessoa_id=None):
    """
    Renderiza a árvore genealógica.
    - Se o usuário estiver logado e associado a uma Pessoa, centraliza nele.
    - Se o usuário não estiver logado ou não tiver Pessoa associada, usa a pessoa_id
      passada, ou a pessoa selecionada na sessão, ou a primeira Pessoa COM OWNER.
    - Árvores são estritamente isoladas por proprietário (owner) para usuários logados.
    - Visitantes (não logados) veem a mensagem para login/cadastro.
    """
    global _global_nodes_map, _global_families_map, _user_ref_for_rel, _pessoa_raiz_global
    _global_nodes_map = {} # Reinicia os mapas globais para cada requisição de árvore
    _global_families_map = {}
    _user_ref_for_rel = None
    _pessoa_raiz_global = None

    pessoa_raiz = None
    user_person_obj_for_tree_ref = None # A pessoa da árvore que representa o 'você'

    current_user_filter = request.user # O usuário logado, usado para filtrar as pessoas

    # 1. Prioridade: Usuário logado e sua Pessoa associada
    if current_user_filter.is_authenticated:
        # Prioriza a pessoa da sessão, se definida e válida
        user_selected_person_id = request.session.get('user_selected_person_id')
        if user_selected_person_id:
            try:
                # AQUI: A pessoa da sessão deve ser válida OU o usuário superuser
                if current_user_filter.is_superuser:
                    user_person_obj_for_tree_ref = Pessoa.objects.get(pk=user_selected_person_id)
                else:
                    user_person_obj_for_tree_ref = get_object_or_404(Pessoa, pk=user_selected_person_id, owner=current_user_filter) # Garante que só pega o que pertence ao user
            except (Pessoa.DoesNotExist, AttributeError) as e:
                # Captura tanto Pessoa.DoesNotExist quanto o erro de pessoa_associada
                user_person_obj_for_tree_ref = None
                if 'user_selected_person_id' in request.session: # Limpa a sessão se a pessoa não existe ou não é do owner
                    del request.session['user_selected_person_id']
                print(f"DEBUG: Error retrieving user_pessoa from session (or it was invalid): {e}")

        # 2. Se a sessão não definiu 'user_pessoa', tenta a pessoa_associada (relacionamento OneToOne)
        if not user_person_obj_for_tree_ref:
            try:
                user_person_obj_for_tree_ref = current_user_filter.pessoa_associada
            except (ObjectDoesNotExist, AttributeError) as e:
                user_person_obj_for_tree_ref = None
                # print(f"DEBUG: user.pessoa_associada not found or attribute error: {e}") # Comentado para não poluir log


        # 3. Se ainda não encontrou, tenta a primeira pessoa que o usuário possui
        if not user_person_obj_for_tree_ref:
            user_person_obj_for_tree_ref = Pessoa.objects.filter(owner=current_user_filter).order_by('data_nascimento').first()
            # Opcional: Se encontrou uma primeira pessoa aqui e NADA estava na sessão,
            # pode considerar defini-la automaticamente na sessão para consistência futura.
            # if user_pessoa and not self.request.session.get('user_selected_person_id'):
            #       self.request.session['user_selected_person_id'] = user_pessoa.pk


        # Agora define a pessoa raiz da árvore e a referência para parentesco
        _user_ref_for_rel = user_person_obj_for_tree_ref
        pessoa_raiz = user_person_obj_for_tree_ref

        # Se mesmo assim, logado, mas não tem pessoa_associada e nem pessoas próprias, exibe mensagem
        if not pessoa_raiz:
            message = "Você ainda não tem pessoas cadastradas na sua árvore. Comece adicionando uma!"
            return render(request, 'pessoas/arvore_simples.html', {'message': message})

    else: # Usuário NÃO está logado (anônimo)
        message = "Nenhuma pessoa cadastrada para exibir a árvore. Faça login ou cadastre-se para criar sua própria árvore!"
        return render(request, 'pessoas/arvore_simples.html', {'message': message})


    # 2. Se a árvore já foi definida por um usuário logado e possui raiz, continue
    # Se chegamos aqui, `pessoa_raiz` JÁ FOI DEFINIDA para o usuário logado (ou a mensagem de árvore vazia foi exibida)
    # ou somos um superuser.

    # Se um `pessoa_id` foi passado na URL, e o usuário é logado, verifica se pertence a ele
    if pessoa_id:
        if current_user_filter.is_authenticated:
            # A pessoa da URL DEVE pertencer ao usuário logado (ou ser superuser)
            if current_user_filter.is_superuser:
                pessoa_raiz = get_object_or_404(Pessoa, pk=pessoa_id) # Superuser pode ver qualquer ID
            else:
                pessoa_raiz = get_object_or_404(Pessoa, pk=pessoa_id, owner=current_user_filter) # Apenas pessoas do owner

        # Se mudamos a raiz via URL, atualiza o _user_ref_for_rel (se for do mesmo owner)
        if _user_ref_for_rel and pessoa_raiz and pessoa_raiz.owner != _user_ref_for_rel.owner and not current_user_filter.is_superuser:
            messages.warning(request, "Você está visualizando a árvore de uma pessoa que não é sua. A lógica de parentesco pode não ser precisa.")
        elif not _user_ref_for_rel and pessoa_raiz:
            _user_ref_for_rel = pessoa_raiz

    _pessoa_raiz_global = pessoa_raiz # Define a raiz global para a geração da árvore

    # Popula o _global_nodes_map e _global_families_map
    _populate_all_tree_data(pessoa_raiz, current_user_filter)

    # Lógica para coletar e agregar dados de região (filtrada pelas pessoas que são visíveis)
    regioes_contagem = {}

    for person_pk, person_data in _global_nodes_map.items():
        # ATENÇÃO: As pessoas em _global_nodes_map JÁ FORAM FILTRADAS por owner via _get_person_data()
        if 'estado_nascimento' in person_data and person_data['estado_nascimento']:
            estado_uf = person_data['estado_nascimento'].upper()
            if estado_uf in UF_TO_REGIAO:
                regiao = UF_TO_REGIAO[estado_uf]
                regioes_contagem[regiao] = regioes_contagem.get(regiao, 0) + 1
            else:
                regioes_contagem['Outras Regiões/Estrangeiro'] = regioes_contagem.get('Outras Regiões/Estrangeiro', 0) + 1

    regioes_para_template = [{'regiao': regiao, 'count': count} for regiao, count in regioes_contagem.items()]
    regioes_para_template.sort(key=lambda x: x['count'], reverse=True)


    # --- Construção dos Níveis de Exibição (Person-Centric BFS) ---
    person_to_level = {}

    if pessoa_raiz:
        queue_for_levels = deque([(pessoa_raiz, 0)])
        visited_for_levels = {pessoa_raiz.pk}
    else:
        queue_for_levels = deque([])
        visited_for_levels = set()

    min_level = 0
    max_level = 0

    while queue_for_levels:
        current_person, level = queue_for_levels.popleft()

        # AQUI: A pessoa que está sendo adicionada a `person_to_level`
        # e `visited_for_levels` DEVE ser visível ao usuário.
        # Essa visibilidade já é controlada pelo _global_nodes_map que é filtrado pelo owner.
        if current_person.pk not in _global_nodes_map: # Se não está no mapa global, já foi filtrada em _get_person_data
            print(f"DEBUG: Skipping {current_person.nome} (ID: {current_person.pk}) in level construction - not in _global_nodes_map.")
            continue

        person_to_level[current_person.pk] = level
        min_level = min(min_level, level)
        max_level = max(max_level, level)

        # Adicionar pais
        if current_person.pai and current_person.pai.pk not in visited_for_levels:
            if current_person.pai.pk in _global_nodes_map: # Garante que o pai é visível ao owner
                queue_for_levels.append((current_person.pai, level - 1))
                visited_for_levels.add(current_person.pai.pk)
            else:
                print(f"DEBUG: Parent {current_person.pai.nome} (ID: {current_person.pai.pk}) not in _global_nodes_map, skipped for levels queue.")

        if current_person.mae and current_person.mae.pk not in visited_for_levels:
            if current_person.mae.pk in _global_nodes_map: # Garante que a mãe é visível ao owner
                queue_for_levels.append((current_person.mae, level - 1))
                visited_for_levels.add(current_person.mae.pk)
            else:
                print(f"DEBUG: Mother {current_person.mae.nome} (ID: {current_person.mae.pk}) not in _global_nodes_map, skipped for levels queue.")

        # Cônjuges:
        spouses_in_this_level_to_add = set()
        # Cônjuge direto
        if current_person.conjuge and current_person.conjuge.pk in _global_nodes_map and current_person.conjuge.pk not in visited_for_levels:
            spouses_in_this_level_to_add.add(current_person.conjuge)
        elif current_person.conjuge and current_person.conjuge.pk not in _global_nodes_map:
            print(f"DEBUG: Direct conjuge {current_person.conjuge.nome} (ID: {current_person.conjuge.pk}) not in _global_nodes_map, skipped for levels queue.")

        # Cônjuges reversos
        for reverse_spouse in Pessoa.objects.filter(conjuge=current_person):
            if reverse_spouse.pk in _global_nodes_map and reverse_spouse.pk not in visited_for_levels:
                spouses_in_this_level_to_add.add(reverse_spouse)
            elif reverse_spouse.pk not in _global_nodes_map:
                print(f"DEBUG: Reverse conjuge {reverse_spouse.nome} (ID: {reverse_spouse.pk}) not in _global_nodes_map, skipped for levels queue.")

        for spouse_obj in spouses_in_this_level_to_add:
            person_to_level[spouse_obj.pk] = level
            visited_for_levels.add(spouse_obj.pk)

        # Filhos:
        current_person_family_ids = set()
        for family_id, family_data in _global_families_map.items():
            if (family_data['husband_id'] == current_person.pk or family_data['wife_id'] == current_person.pk):
                current_person_family_ids.add(family_id)

        for family_id in current_person_family_ids:
            for child_pk in _global_families_map[family_id]['children_ids']:
                if child_pk not in visited_for_levels:
                    if child_pk in _global_nodes_map: # Garante que o filho é visível ao owner
                        child_obj = Pessoa.objects.get(pk=child_pk)
                        queue_for_levels.append((child_obj, level + 1))
                        visited_for_levels.add(child_obj.pk)
                    else:
                        print(f"DEBUG: Child {child_pk} not in _global_nodes_map, skipped for levels queue.")

    final_tree_structure_for_template = []

    # Criar um dicionário para agrupar as pessoas por nível
    levels_data = {}
    for person_pk, level_val in person_to_level.items():
        if level_val not in levels_data:
            levels_data[level_val] = []
        levels_data[level_val].append(_global_nodes_map[person_pk])

    # Ordenar os níveis e processar cada uno
    sorted_levels = sorted(levels_data.keys())

    for level_idx in sorted_levels:
        persons_in_this_level = levels_data[level_idx]

        grouped_persons_by_type = {}
        handled_pks_in_level = set() # Novo conjunto para rastrear pessoas já agrupadas neste nível

        # 1. Agrupar cônjuges (casais)
        for family_id, family_data in _global_families_map.items():
            husband_id = family_data['husband_id']
            wife_id = family_data['wife_id']

            # Se ambos os cônjuges existem neste nível e não foram tratados ainda
            if husband_id and wife_id and \
               husband_id in person_to_level and person_to_level[husband_id] == level_idx and \
               wife_id in person_to_level and person_to_level[wife_id] == level_idx and \
               husband_id not in handled_pks_in_level and wife_id not in handled_pks_in_level:

                # Certifica-se que ambos estão no _global_nodes_map (já filtrado pelo owner)
                if husband_id in _global_nodes_map and wife_id in _global_nodes_map:
                    group_key = f"Couple_{min(husband_id, wife_id)}_{max(husband_id, wife_id)}"
                    grouped_persons_by_type[group_key] = [
                        _global_nodes_map[husband_id],
                        _global_nodes_map[wife_id]
                    ]
                    handled_pks_in_level.add(husband_id)
                    handled_pks_in_level.add(wife_id)
                else:
                    print(f"DEBUG: Couple (IDs: {husband_id}, {wife_id}) not grouped (one or both not in _global_nodes_map).")


        # 2. Agrupar irmãos e pessoas solo
        for person_data in persons_in_this_level:
            if person_data['id'] in handled_pks_in_level:
                continue # Já foi tratado como parte de um casal

            # Verificar se a pessoa está no _global_nodes_map (já filtrado pelo owner)
            if person_data['id'] not in _global_nodes_map:
                print(f"DEBUG: Person {person_data['nome']} (ID: {person_data['id']}) not grouped as solo/sibling (not in _global_nodes_map).")
                continue

            parent_key_for_siblings = f"Parents_{person_data['pai_id'] if person_data['pai_id'] else 'None'}_{person_data['mae_id'] if person_data['mae_id'] else 'None'}"

            if parent_key_for_siblings not in grouped_persons_by_type:
                grouped_persons_by_type[parent_key_for_siblings] = []

            grouped_persons_by_type[parent_key_for_siblings].append(person_data)
            handled_pks_in_level.add(person_data['id']) # Marque como handled

        # Ordena os grupos e as pessoas dentro de cada grupo
        sorted_level_nodes = []

        sorted_group_keys = sorted(grouped_persons_by_type.keys(), key=lambda k: (
            0 if k.startswith("Couple_") else (1 if k.startswith("Parents_") and "None" not in k else 2),
            k
        ))

        for group_key in sorted_group_keys:
            group_nodes = grouped_persons_by_type[group_key]
            if group_key.startswith("Couple_"):
                group_nodes.sort(key=lambda x: (x['genero'], x['nome'])) # 'M' antes de 'F'
            else: # Irmãos ou solos
                group_nodes.sort(key=lambda x: (x['data_nascimento'] if x['data_nascimento'] else '9999-01-01', x['nome']))

            group_type = "couple-group" if group_key.startswith("Couple_") else "sibling-group"
            if group_key.startswith("Parents_None_None"):
                group_type = "solo-group"

            sorted_level_nodes.append({'group_key': group_key, 'group_type': group_type, 'nodes': group_nodes})

        final_tree_structure_for_template.append({
            'level': level_idx,
            'grouped_nodes': sorted_level_nodes
        })

    context = {
        'all_tree_data': {
            'persons': _global_nodes_map,
            'families': _global_families_map,
        },
        'root_display_unit_id': pessoa_raiz.pk if pessoa_raiz else None,
        'user_pessoa': user_person_obj_for_tree_ref,
        'tree_levels': final_tree_structure_for_template,
        'regioes_familiares': regioes_para_template,
    }
    return render(request, 'pessoas/arvore_simples.html', context)


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Conta criada com sucesso para {user.username}!")
            return redirect('home_page')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})

def excluir_pessoa(request, pk):
    try:
        pessoa = get_object_or_404(Pessoa, pk=pk)
        if request.user.is_authenticated and (pessoa.owner == request.user or request.user.is_superuser):
            nome_pessoa = pessoa.nome
            pessoa.delete()
            messages.success(request, f"'{nome_pessoa}' foi removido(a) da árvore com sucesso.")
        else:
            messages.error(request, "Você não tem permissão para excluir esta pessoa.")
    except Exception as e:
        messages.error(request, f"Ocorreu um erro ao excluir o membro: {e}")

    return redirect('arvore_genealogica_default')