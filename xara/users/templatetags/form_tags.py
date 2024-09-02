from django import template
import re

register = template.Library()



@register.filter(name='addclass')
def addclass(value, arg):
    return value.as_widget(attrs={'class': arg})


@register.filter
def getattribute(value, arg):
    """
    Gets an attribute of an object dynamically from a string name
    """
    if hasattr(value, str(arg)):
        return getattr(value, arg)
    elif isinstance(value, dict) and arg in value:
        return value[arg]
    elif isinstance(arg, int) and isinstance(value, (list, tuple)) and len(value) > arg:
        return value[arg]
    else:
        return None

@register.filter
def index(value, arg):
    """
    Returns the item at index 'arg' in the list 'value'
    """
    try:
        return value[int(arg)]
    except (IndexError, ValueError, TypeError):
        return None

@register.filter
def get_item(dictionary, key):
    """
    Returns the value for the given key in the dictionary
    """
    return dictionary.get(key)