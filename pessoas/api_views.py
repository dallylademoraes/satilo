# pessoas/api_views.py

from collections import deque
from datetime import date

# Importações DRF
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework import serializers
from rest_framework.views import APIView
from django.db.models import Q

# Importações Django
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

# Importações do seu app
from .models import Pessoa
from .serializers import PessoaSerializer


# Variáveis globais para a lógica da árvore na API (podem ser locais para a função, mas mantidas por consistência)
_global_nodes_map_api = {}
_global_families_map_api = {}
_user_ref_for_rel_api = None 
UF_TO_REGIAO = {
    'AC': 'Norte', 'AM': 'Norte', 'AP': 'Norte', 'PA': 'Norte', 'RO': 'Norte', 'RR': 'Norte', 'TO': 'Norte',
    'AL': 'Nordeste', 'BA': 'Nordeste', 'CE': 'Nordeste', 'MA': 'Nordeste', 'PB': 'Nordeste',
    'PE': 'Nordeste', 'PI': 'Piauí', 'RN': 'Nordeste', 'SE': 'Nordeste',
    'DF': 'Centro-Oeste', 'GO': 'Centro-Oeste', 'MS': 'Centro-Oeste', 'MT': 'Centro-Oeste',
    'ES': 'Sudeste', 'MG': 'Sudeste', 'SP': 'Sudeste',
    'RJ': 'Sudeste',
    'PR': 'Sul', 'RS': 'Sul', 'SC': 'Sul',
}

def _get_person_data_for_api(person_obj, current_user_filter, root_person_for_rel, request_obj):
    if not person_obj or not hasattr(person_obj, 'pk'):
        return None

    if person_obj.owner != current_user_filter and not current_user_filter.is_superuser:
        return None
        
    if person_obj.pk in _global_nodes_map_api:
        return _global_nodes_map_api[person_obj.pk]

    # ESTA É A ÚNICA SERIALIZAÇÃO DE PessoaSerializer(person_obj)
    data = PessoaSerializer(person_obj, context={'request': request_obj}).data
    data['is_root_display_node'] = (person_obj.pk == root_person_for_rel.pk) if root_person_for_rel else False
    data['is_user_selected'] = (person_obj.pk == root_person_for_rel.pk) if root_person_for_rel else False
    data['relacao'] = person_obj.get_relationship_to_user(root_person_for_rel) if root_person_for_rel else "Desconhecida"

    _global_nodes_map_api[person_obj.pk] = data
    return data

def _add_family_unit_to_global_map_api(husband_obj, wife_obj, current_user_filter, get_queryset_func, root_person_for_rel, request_obj):
    husband_pk = str(husband_obj.pk) if husband_obj else 'none'
    wife_pk = str(wife_obj.pk) if wife_obj else 'none'
    family_id = f"family_{husband_pk}_{wife_pk}"

    if family_id in _global_families_map_api:
        return _global_families_map_api[family_id]

    valid_husband = None
    if husband_obj and (husband_obj.owner == current_user_filter or current_user_filter.is_superuser):
        valid_husband = husband_obj
    
    valid_wife = None
    if wife_obj and (wife_obj.owner == current_user_filter or current_user_filter.is_superuser):
        valid_wife = wife_obj

    if not valid_husband and not valid_wife:
        return None

    family_data = {
        'id': family_id,
        'type': 'family_unit',
        'husband_id': valid_husband.pk if valid_husband else None,
        'wife_id': valid_wife.pk if valid_wife else None,
        'children_ids': [],
    }
    _global_families_map_api[family_id] = family_data

    _get_person_data_for_api(valid_husband, current_user_filter, root_person_for_rel, request_obj)
    _get_person_data_for_api(valid_wife, current_user_filter, root_person_for_rel, request_obj)

    children_qs = Pessoa.objects.none()
    base_children_query = get_queryset_func()

    if valid_husband and valid_wife:
        children_qs = base_children_query.filter(pai=valid_husband, mae=valid_wife)
    elif valid_husband:
        children_qs = base_children_query.filter(pai=valid_husband, mae__isnull=True)
    elif valid_wife:
        children_qs = base_children_query.filter(mae=valid_wife, pai__isnull=True)
    
    for child_obj in children_qs.distinct().order_by('data_nascimento'):
        if _get_person_data_for_api(child_obj, current_user_filter, root_person_for_rel, request_obj):
            family_data['children_ids'].append(child_obj.pk)
    return family_data


class PessoaViewSet(viewsets.ModelViewSet):
    queryset = Pessoa.objects.all().order_by('nome')
    serializer_class = PessoaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Pessoa.objects.all().order_by('nome')
        return Pessoa.objects.filter(owner=self.request.user).order_by('nome')

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(owner=self.request.user)
        else:
            raise serializers.ValidationError("Você precisa estar logado para criar uma pessoa.")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=True, methods=['get'], url_path='arvore')
    def arvore_detalhes(self, request, pk=None):
        global _global_nodes_map_api, _global_families_map_api, _user_ref_for_rel_api
        _global_nodes_map_api = {}
        _global_families_map_api = {}
        _user_ref_for_rel_api = None

        try:
            root_person = self.get_queryset().get(pk=pk)
        except Pessoa.DoesNotExist:
            return Response({"detail": "Pessoa não encontrada ou você não tem permissão para acessá-la."}, status=404)

        _user_ref_for_rel_api = root_person

        queue_persons = deque([root_person])
        visited_persons_pks = {root_person.pk}
        visited_family_ids = set()

        _get_person_data_for_api(root_person, request.user, root_person, request)

        while queue_persons:
            current_person_obj = queue_persons.popleft()

            pai_obj = current_person_obj.pai
            mae_obj = current_person_obj.mae
            parent_family = _add_family_unit_to_global_map_api(pai_obj, mae_obj, request.user, self.get_queryset, root_person, request)
            if parent_family and parent_family['id'] not in visited_family_ids:
                visited_family_ids.add(parent_family['id'])
                if pai_obj and pai_obj.pk not in visited_persons_pks and pai_obj.pk in _global_nodes_map_api:
                    queue_persons.append(pai_obj)
                    visited_persons_pks.add(pai_obj.pk)
                if mae_obj and mae_obj.pk not in visited_persons_pks and mae_obj.pk in _global_nodes_map_api:
                    queue_persons.append(mae_obj)
                    visited_persons_pks.add(mae_obj.pk)

            spouses_of_current_person = set()
            if current_person_obj.conjuge:
                spouses_of_current_person.add(current_person_obj.conjuge)
            for spouse_of_current in Pessoa.objects.filter(conjuge=current_person_obj):
                spouses_of_current_person.add(spouse_of_current)
            if None in spouses_of_current_person:
                spouses_of_current_person.remove(None)
            
            for spouse_obj in spouses_of_current_person:
                husband_candidate = current_person_obj if current_person_obj.genero == 'M' else spouse_obj
                wife_candidate = current_person_obj if current_person_obj.genero == 'F' else spouse_obj

                child_family_unit = _add_family_unit_to_global_map_api(husband_candidate, wife_candidate, request.user, self.get_queryset, root_person, request)
                if child_family_unit and child_family_unit['id'] not in visited_family_ids:
                    visited_family_ids.add(child_family_unit['id'])
                    if spouse_obj and spouse_obj.pk not in visited_persons_pks and spouse_obj.pk in _global_nodes_map_api:
                        queue_persons.append(spouse_obj)
                        visited_persons_pks.add(spouse_obj.pk)
                    for child_pk in child_family_unit['children_ids']:
                        if child_pk not in visited_persons_pks and child_pk in _global_nodes_map_api:
                            child_obj = Pessoa.objects.get(pk=child_pk)
                            queue_persons.append(child_obj)
                            visited_persons_pks.add(child_obj.pk)

            single_parent_family = None
            if current_person_obj.genero == 'M':
                single_parent_family = _add_family_unit_to_global_map_api(current_person_obj, None, request.user, self.get_queryset, root_person, request)
            elif current_person_obj.genero == 'F':
                single_parent_family = _add_family_unit_to_global_map_api(None, current_person_obj, request.user, self.get_queryset, root_person, request)
            
            if single_parent_family and single_parent_family['id'] not in visited_family_ids:
                visited_family_ids.add(single_parent_family['id'])
                for child_pk in single_parent_family['children_ids']:
                    if child_pk not in visited_persons_pks and child_pk in _global_nodes_map_api:
                        child_obj = Pessoa.objects.get(pk=child_pk)
                        queue_persons.append(child_obj)
                        visited_persons_pks.add(child_obj.pk)
            
            if current_person_obj.pai and current_person_obj.mae:
                parents_family_unit = _add_family_unit_to_global_map_api(current_person_obj.pai, current_person_obj.mae, request.user, self.get_queryset, root_person, request)
                if parents_family_unit:
                    for sibling_pk in parents_family_unit['children_ids']:
                        if sibling_pk != current_person_obj.pk and sibling_pk not in visited_persons_pks:
                            if sibling_pk in _global_nodes_map_api:
                                sibling_obj = Pessoa.objects.get(pk=sibling_pk)
                                queue_persons.append(sibling_obj)
                                visited_persons_pks.add(sibling_obj.pk)

        regioes_contagem = {}
        for person_pk, person_data in _global_nodes_map_api.items():
            if 'estado_nascimento' in person_data and person_data['estado_nascimento']:
                estado_uf = person_data['estado_nascimento'].upper()
                if estado_uf in UF_TO_REGIAO:
                    regiao = UF_TO_REGIAO[estado_uf]
                    regioes_contagem[regiao] = regioes_contagem.get(regiao, 0) + 1
                else:
                    regioes_contagem['Outras Regiões/Estrangeiro'] = regioes_contagem.get('Outras Regiões/Estrangeiro', 0) + 1

        regioes_para_template = [{'regiao': regiao, 'count': count} for regiao, count in regioes_contagem.items()]
        regioes_para_template.sort(key=lambda x: x['count'], reverse=True)

        person_to_level = {}
        queue_for_levels = deque([(root_person, 0)])
        visited_for_levels = {root_person.pk}

        while queue_for_levels:
            current_person_for_level, level = queue_for_levels.popleft()
            if current_person_for_level.pk not in _global_nodes_map_api:
                continue

            person_to_level[current_person_for_level.pk] = level

            if current_person_for_level.pai and current_person_for_level.pai.pk not in visited_for_levels and current_person_for_level.pai.pk in _global_nodes_map_api:
                queue_for_levels.append((current_person_for_level.pai, level - 1))
                visited_for_levels.add(current_person_for_level.pai.pk)
            if current_person_for_level.mae and current_person_for_level.mae.pk not in visited_for_levels and current_person_for_level.mae.pk in _global_nodes_map_api:
                queue_for_levels.append((current_person_for_level.mae, level - 1))
                visited_for_levels.add(current_person_for_level.mae.pk)

            spouses_in_this_level_to_add = set()
            if current_person_for_level.conjuge and current_person_for_level.conjuge.pk in _global_nodes_map_api and current_person_for_level.conjuge.pk not in visited_for_levels:
                spouses_in_this_level_to_add.add(current_person_for_level.conjuge)
            for reverse_spouse in Pessoa.objects.filter(conjuge=current_person_for_level):
                if reverse_spouse.pk in _global_nodes_map_api and reverse_spouse.pk not in visited_for_levels:
                    spouses_in_this_level_to_add.add(reverse_spouse)

            for spouse_obj in spouses_in_this_level_to_add:
                person_to_level[spouse_obj.pk] = level
                visited_for_levels.add(spouse_obj.pk)

            current_person_family_ids = set()
            for family_id, family_data in _global_families_map_api.items():
                if (family_data['husband_id'] == current_person_for_level.pk or family_data['wife_id'] == current_person_for_level.pk):
                    current_person_family_ids.add(family_id)

            for family_id in current_person_family_ids:
                for child_pk in _global_families_map_api[family_id]['children_ids']:
                    if child_pk not in visited_for_levels and child_pk in _global_nodes_map_api:
                        child_obj = Pessoa.objects.get(pk=child_pk)
                        queue_for_levels.append((child_obj, level + 1))
                        visited_for_levels.add(child_obj.pk)

        final_tree_structure_for_template = []
        levels_data = {}
        for person_pk, level_val in person_to_level.items():
            if level_val not in levels_data:
                levels_data[level_val] = []
            levels_data[level_val].append(_global_nodes_map_api[person_pk])
        
        sorted_levels = sorted(levels_data.keys())

        for level_idx in sorted_levels:
            persons_in_this_level = levels_data[level_idx]
            grouped_persons_by_type = {}
            handled_pks_in_level = set()

            for family_id, family_data in _global_families_map_api.items():
                husband_id = family_data['husband_id']
                wife_id = family_data['wife_id']
                if husband_id and wife_id and \
                   husband_id in person_to_level and person_to_level[husband_id] == level_idx and \
                   wife_id in person_to_level and person_to_level[wife_id] == level_idx and \
                   husband_id not in handled_pks_in_level and wife_id not in handled_pks_in_level:
                    if husband_id in _global_nodes_map_api and wife_id in _global_nodes_map_api:
                        group_key = f"Couple_{min(husband_id, wife_id)}_{max(husband_id, wife_id)}"
                        grouped_persons_by_type[group_key] = [
                            _global_nodes_map_api[husband_id],
                            _global_nodes_map_api[wife_id]
                        ]
                        handled_pks_in_level.add(husband_id)
                        handled_pks_in_level.add(wife_id)

            for person_data in persons_in_this_level:
                if person_data['id'] in handled_pks_in_level:
                    continue
                if person_data['id'] not in _global_nodes_map_api:
                    continue

                parent_key_for_siblings = f"Parents_{person_data['pai'] if person_data['pai'] else 'None'}_{person_data['mae'] if person_data['mae'] else 'None'}"
                if parent_key_for_siblings not in grouped_persons_by_type:
                    grouped_persons_by_type[parent_key_for_siblings] = []
                grouped_persons_by_type[parent_key_for_siblings].append(person_data)
                handled_pks_in_level.add(person_data['id'])

            sorted_level_nodes = []
            sorted_group_keys = sorted(grouped_persons_by_type.keys(), key=lambda k: (
                0 if k.startswith("Couple_") else (1 if k.startswith("Parents_") and "None" not in k else 2),
                k
            ))
            for group_key in sorted_group_keys:
                group_nodes = grouped_persons_by_type[group_key]
                if group_key.startswith("Couple_"):
                    group_nodes.sort(key=lambda x: (x['genero'], x['nome']))
                else:
                    group_nodes.sort(key=lambda x: (x['data_nascimento'] if x['data_nascimento'] else '9999-01-01', x['nome']))
                
                group_type = "couple-group" if group_key.startswith("Couple_") else "sibling-group"
                if group_key.startswith("Parents_None_None"):
                    group_type = "solo-group"
                sorted_level_nodes.append({'group_key': group_key, 'group_type': group_type, 'nodes': group_nodes})

            final_tree_structure_for_template.append({
                'level': level_idx,
                'grouped_nodes': sorted_level_nodes
            })

        return Response({
            'root_person': _global_nodes_map_api.get(root_person.pk), # Já é um dicionário serializado
            'persons': list(_global_nodes_map_api.values()), # Já são dicionários serializados
            'families': list(_global_families_map_api.values()),
            'tree_levels': final_tree_structure_for_template,
            'regioes_familiares': regioes_para_template,
        })


class RegisterUserAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        form = UserCreationForm(request.data)
        if form.is_valid():
            user = form.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                "message": "Usuário registrado com sucesso.",
                "user_id": user.pk,
                "username": user.username,
                "token": token.key
            }, status=status.HTTP_201_CREATED)
        return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username
        })