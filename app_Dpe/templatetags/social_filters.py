from django import template

register = template.Library()
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Récupère un élément d'un dictionnaire par sa clé"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def get_social_file_by_enfant(social_files, enfant_id):
    if social_files is None:
        return None
    return social_files.filter(enfant_id=enfant_id).first()