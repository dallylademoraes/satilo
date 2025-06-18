# satilo/pessoas/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from .models import Pessoa
from .forms import PessoaForm, UserRegistrationForm # Importe UserRegistrationForm
from datetime import date
from collections import deque
from django.contrib.auth import login # Importe a função login

# ... (suas variáveis globais e mapeamento UF_TO_REGIAO) ...
_global_nodes_map = {}
_global_families_map = {}
_user_ref_for_rel = None
_pessoa_raiz_global = None

UF_TO_REGIAO = {
    'AC': 'Norte', 'AM': 'Norte', 'AP': 'Norte', 'PA': 'Norte', 'RO': 'Norte', 'RR': 'Norte', 'TO': 'Norte',
    'AL': 'Nordeste', 'BA': 'Nordeste', 'CE': 'Nordeste', 'MA': 'Nordeste', 'PB': 'Nordeste',
    'PE': 'Nordeste', 'PI': 'Piauí', 'RN': 'Nordeste', 'SE': 'Nordeste',
    'DF': 'Centro-Oeste', 'GO': 'Centro-Oeste', 'MS': 'Centro-Oeste', 'MT': 'Centro-Oeste',
    'ES': 'Sudeste', 'MG': 'Sudeste', 'RJ': 'Sudeste', 'SP': 'Sudeste',
    'PR': 'Sul', 'RS': 'Sul', 'SC': 'Sul',
}

def _get_person_data(person_obj):
    global _global_nodes_map, _user_ref_for_rel, _pessoa_raiz_global

    if not person_obj: return None

    if not hasattr(person_obj, 'pk'):
        return None

    if person_obj.pk in _global_nodes_map:
        return _global_nodes_map[person_obj.pk]

    data = {
        'id': person_obj.pk,
        'nome': person_obj.nome,
        'foto_url': person_obj.foto.url if person_obj.foto else person_obj.get_default_photo_url(),
        'data_nascimento': person_obj.data_nascimento,
        'data_falecimento': person_obj.data_falecimento,
        'data_falecimento_incerta': person_obj.data_falecimento_incerta,
        'genero': person_obj.genero,
        'relacao': person_obj.get_relationship_to_user(_user_ref_for_rel),
        'idade': person_obj.get_age(),
        'status_vida': person_obj.get_status_vida_display(),
        'type': 'person',
        'is_root_display_node': (person_obj.pk == _pessoa_raiz_global.pk),
        'is_user_selected': (person_obj.pk == (_user_ref_for_rel.pk if _user_ref_for_rel else None)),
        'historia_pessoal': person_obj.historia_pessoal,
        'local_nascimento': person_obj.local_nascimento,
        'estado_nascimento': person_obj.estado_nascimento,
        'pai_id': person_obj.pai.pk if person_obj.pai else None,
        'mae_id': person_obj.mae.pk if person_obj.mae else None,
        'child_family_unit_ids': [],
        'parent_family_id': None,
    }
    _global_nodes_map[person_obj.pk] = data
    return data

def _add_family_unit_to_global_map(husband_obj, wife_obj):
    global _global_families_map, _global_nodes_map

    family_key_parts = []
    if husband_obj: family_key_parts.append(str(husband_obj.pk))
    else: family_key_parts.append('none')
    if wife_obj: family_key_parts.append(str(wife_obj.pk))
    else: family_key_parts.append('none')
    family_id = f"family_{'_'.join(family_key_parts)}"

    if family_id in _global_families_map:
        return _global_families_map[family_id]

    family_data = {
        'id': family_id,
        'type': 'family_unit',
        'husband_id': husband_obj.pk if husband_obj else None,
        'wife_id': wife_obj.pk if wife_obj else None,
        'children_ids': [],
    }
    _global_families_map[family_id] = family_data

    _get_person_data(husband_obj)
    _get_person_data(wife_obj)

    children_qs = Pessoa.objects.none()
    if husband_obj and wife_obj:
        children_qs = Pessoa.objects.filter(pai=husband_obj, mae=wife_obj)
    elif husband_obj:
        children_qs = Pessoa.objects.filter(pai=husband_obj, mae__isnull=True)
    elif wife_obj:
        children_qs = Pessoa.objects.filter(mae=wife_obj, pai__isnull=True)

    if husband_obj:
        children_qs = children_qs | Pessoa.objects.filter(pai=husband_obj, mae__isnull=True)
    if wife_obj:
        children_qs = children_qs | Pessoa.objects.filter(mae=wife_obj, pai__isnull=True)


    for child_obj in children_qs.distinct().order_by('data_nascimento'):
        _get_person_data(child_obj)
        if child_obj.pk not in family_data['children_ids']:
            family_data['children_ids'].append(child_obj.pk)
            if _global_nodes_map[child_obj.pk].get('parent_family_id') is None:
                _global_nodes_map[child_obj.pk]['parent_family_id'] = family_id

    return family_data

def _populate_all_tree_data(start_person_obj_orm):
    global _global_nodes_map, _global_families_map, _user_ref_for_rel, _pessoa_raiz_global

    if not start_person_obj_orm: return

    queue = deque()
    queue.append(start_person_obj_orm)

    queued_pks = {start_person_obj_orm.pk}

    while queue:
        current_obj_orm = queue.popleft()

        current_person_data = _get_person_data(current_obj_orm)

        if current_obj_orm.pai or current_obj_orm.mae:
            parent_family_data = _add_family_unit_to_global_map(current_obj_orm.pai, current_obj_orm.mae)
            if current_person_data.get('parent_family_id') is None:
                    current_person_data['parent_family_id'] = parent_family_data['id']

            if current_obj_orm.pai and current_obj_orm.pai.pk not in queued_pks:
                queue.append(current_obj_orm.pai)
                queued_pks.add(current_obj_orm.pai.pk)
            if current_obj_orm.mae and current_obj_orm.mae.pk not in queued_pks:
                queue.append(current_obj_orm.mae)
                queued_pks.add(current_obj_orm.mae.pk)

        partners_with_children = set()
        for child in current_obj_orm.filhos_do_pai.all():
            if child.mae: partners_with_children.add(child.mae)
            else: partners_with_children.add(None)
        for child in current_obj_orm.filhos_da_mae.all():
            if child.pai: partners_with_children.add(child.pai)
            else: partners_with_children.add(None)

        if current_obj_orm.filhos_do_pai.filter(mae__isnull=True).exists():
            partners_with_children.add(None)
        if current_obj_orm.filhos_da_mae.filter(pai__isnull=True).exists():
            partners_with_children.add(None)

        for partner_obj in partners_with_children:
            husband_obj = current_obj_orm if current_obj_orm.genero == 'M' else partner_obj
            wife_obj = current_obj_orm if current_obj_orm.genero == 'F' else partner_obj

            if current_obj_orm.genero == 'M':
                husband_obj = current_obj_orm
            elif current_obj_orm.genero == 'F':
                wife_obj = current_obj_orm

            child_family_data = _add_family_unit_to_global_map(husband_obj, wife_obj)
            if child_family_data['id'] not in current_person_data['child_family_unit_ids']:
                current_person_data['child_family_unit_ids'].append(child_family_data['id'])

            for child_of_family_id in child_family_data['children_ids']:
                child_obj_orm = Pessoa.objects.get(pk=child_of_family_id)
                if child_obj_orm.pk not in queued_pks:
                    queue.append(child_obj_orm)
                    queued_pks.add(child_obj_orm.pk)


def home_page(request):
    return render(request, 'pessoas/home.html', {})

class ListaPessoas(ListView):
    model = Pessoa
    template_name = 'pessoas/lista_pessoas.html'
    context_object_name = 'pessoas'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_pessoa_id = self.request.session.get('user_selected_person_id')
        user_pessoa = None
        if user_pessoa_id:
            try:
                user_pessoa = Pessoa.objects.get(pk=user_pessoa_id)
            except Pessoa.DoesNotExist:
                user_pessoa = None
                del self.request.session['user_selected_person_id']

        if not user_pessoa:
            user_pessoa = Pessoa.objects.first()

        for pessoa in context['pessoas']:
            if user_pessoa:
                pessoa.relacao_com_principal = pessoa.get_relationship_to_user(user_pessoa)
                pessoa.is_user_selected = (pessoa.pk == user_pessoa.pk)
            else:
                pessoa.relacao_com_principal = "Pessoa na Árvore"
                pessoa.is_user_selected = False

            pessoa.status_vida_display = pessoa.get_status_vida_display()
            pessoa.idade = pessoa.get_age()
            pessoa.local_nascimento = pessoa.local_nascimento
            pessoa.estado_nascimento = pessoa.estado_nascimento
        return context

class CriaPessoa(CreateView):
    model = Pessoa
    template_name = 'pessoas/cria_pessoa.html'
    form_class = PessoaForm
    success_url = reverse_lazy('lista_pessoas')

class EditaPessoa(UpdateView):
    model = Pessoa
    template_name = 'pessoas/cria_pessoa.html'
    form_class = PessoaForm
    success_url = reverse_lazy('lista_pessoas')

def set_user_person(request, person_id):
    try:
        person = Pessoa.objects.get(pk=person_id)
        request.session['user_selected_person_id'] = person.pk
        messages.success(request, f"'{person.nome}' definido(a) como você.")
    except Pessoa.DoesNotExist:
        messages.error(request, "Pessoa não encontrada para definir como você.")
    return redirect('lista_pessoas')


def arvore_genealogica(request, pessoa_id=None):
    global _global_nodes_map, _global_families_map, _user_ref_for_rel, _pessoa_raiz_global
    _global_nodes_map = {}
    _global_families_map = {}
    _user_ref_for_rel = None
    _pessoa_raiz_global = None

    user_pessoa_id_from_session = request.session.get('user_selected_person_id')

    user_person_obj_for_tree_ref = None
    if user_pessoa_id_from_session:
        try:
            user_person_obj_for_tree_ref = Pessoa.objects.get(pk=user_pessoa_id_from_session)
        except Pessoa.DoesNotExist:
            user_person_obj_for_tree_ref = None
            del request.session['user_selected_person_id']

    pessoa_raiz = None
    if pessoa_id:
        pessoa_raiz = get_object_or_404(Pessoa.objects.all(), pk=pessoa_id)
    elif user_person_obj_for_tree_ref:
        pessoa_raiz = user_person_obj_for_tree_ref
    else:
        ancestrais_sem_pais = Pessoa.objects.filter(pai__isnull=True, mae__isnull=True).order_by('data_nascimento').first()
        if ancestrais_sem_pais:
            pessoa_raiz = ancestrais_sem_pais
        else:
            pessoa_raiz = Pessoa.objects.order_by('data_nascimento').first()
            if pessoa_raiz:
                pass
            else:
                pass


    if not pessoa_raiz:
        return render(request, 'pessoas/arvore_simples.html', {'message': 'Nenhuma pessoa cadastrada para exibir a árvore.'})

    _user_ref_for_rel = user_person_obj_for_tree_ref if user_person_obj_for_tree_ref else pessoa_raiz
    _pessoa_raiz_global = pessoa_raiz

    _populate_all_tree_data(pessoa_raiz)

    # Lógica para coletar e agregar dados de região
    regioes_contagem = {}
    for person_pk, person_data in _global_nodes_map.items():
        if 'estado_nascimento' in person_data and person_data['estado_nascimento']:
            estado_uf = person_data['estado_nascimento'].upper()
            if estado_uf in UF_TO_REGIAO:
                regiao = UF_TO_REGIAO[estado_uf]
                regioes_contagem[regiao] = regioes_contagem.get(regiao, 0) + 1
            else: # Se o estado não está no mapeamento (talvez estrangeiro ou UF inválida)
                regioes_contagem['Outras Regiões/Estrangeiro'] = regioes_contagem.get('Outras Regiões/Estrangeiro', 0) + 1
        # Se 'estado_nascimento' não estiver preenchido, ele não será contado para esta análise

    regioes_para_template = []
    for regiao, count in regioes_contagem.items():
        regioes_para_template.append({'regiao': regiao, 'count': count})

    regioes_para_template.sort(key=lambda x: x['count'], reverse=True)


    tree_levels_data = {}
    person_to_level = {}

    queue_levels = deque([(pessoa_raiz, 0)])
    visited_pks_for_levels = {pessoa_raiz.pk}

    while queue_levels:
        current_obj_orm, level = queue_levels.popleft()

        person_to_level[current_obj_orm.pk] = level

        if current_obj_orm.pai and current_obj_orm.pai.pk not in visited_pks_for_levels:
            queue_levels.append( (current_obj_orm.pai, level - 1) )
            visited_pks_for_levels.add(current_obj_orm.pai.pk)
        if current_obj_orm.mae and current_obj_orm.mae.pk not in visited_pks_for_levels:
            queue_levels.append( (current_obj_orm.mae, level - 1) )
            visited_pks_for_levels.add(current_obj_orm.mae.pk)

        all_children_of_current = Pessoa.objects.filter(pai=current_obj_orm) | Pessoa.objects.filter(mae=current_obj_orm)
        for child_obj_orm in all_children_of_current.distinct():
            if child_obj_orm.pk not in visited_pks_for_levels:
                queue_levels.append( (child_obj_orm, level + 1) )
                visited_pks_for_levels.add(child_obj_orm.pk)

    min_level = min(person_to_level.values()) if person_to_level else 0
    max_level = max(person_to_level.values()) if person_to_level else 0

    final_tree_structure_for_template = []

    for level_idx in range(min_level, max_level + 1):
        people_in_this_level = []
        for person_pk in person_to_level:
            if person_to_level[person_pk] == level_idx:
                people_in_this_level.append(_global_nodes_map[person_pk])

        people_in_this_level.sort(key=lambda x: x['nome'])

        final_tree_structure_for_template.append({
            'level': level_idx,
            'nodes': people_in_this_level
        })

    context = {
        'all_tree_data': {
            'persons': _global_nodes_map,
            'families': _global_families_map,
        },
        'root_display_unit_id': _global_nodes_map[pessoa_raiz.pk].get('parent_family_id') or f"family_{pessoa_raiz.pk}_solo_root",
        'user_pessoa': user_person_obj_for_tree_ref,
        'tree_levels': final_tree_structure_for_template,
        'regioes_familiares': regioes_para_template, # NOVO: Dados das regiões para o template
    }
    return render(request, 'pessoas/arvore_simples.html', context)

# NOVO: View para o registro de usuários
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Faz o login do usuário automaticamente após o cadastro
            messages.success(request, f"Conta criada com sucesso para {user.username}!")
            return redirect('home_page') # Redireciona para a página inicial ou outra página
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/register.html', {'form': form})