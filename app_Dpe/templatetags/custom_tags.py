from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Récupère la valeur d'une clé dans un dictionnaire."""
    if dictionary and key in dictionary:
        return dictionary[key]
    return 'غير معروف'  # Valeur par défaut si l'élément n'existe pas
