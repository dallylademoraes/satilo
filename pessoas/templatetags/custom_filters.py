# satilo/pessoas/templatetags/custom_filters.py

from django import template

register = template.Library()

@register.filter
def startswith(value, arg):
    """
    Verifica se uma string começa com um determinado prefixo.
    Uso: {{ value|startswith:"prefix" }}
    """
    if isinstance(value, str):
        return value.startswith(arg)
    return False

@register.filter
def get_item(dictionary, key):
    """
    Permite acessar um item de um dicionário por chave no template.
    Uso: {{ my_dict|get_item:key }}
    """
    return dictionary.get(key)

@register.filter
def get_children_families_for_person(families_map, person_id):
    """
    Verifica se uma pessoa é pai/mãe em alguma unidade familiar mapeada e tem filhos.
    Usado para determinar se um cartão de pessoa deve mostrar a linha 'has-children'.
    """
    # Itera sobre todas as famílias para ver se esta pessoa é um dos pais em alguma
    for family_data in families_map.values():
        if (family_data['husband_id'] == person_id or family_data['wife_id'] == person_id) and family_data['children_ids']:
            return True
    return False