# satilo/pessoas/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter(name='class_name') 
def class_name(value):
    """Retorna o nome da classe de um objeto."""
    return value.__class__.__name__