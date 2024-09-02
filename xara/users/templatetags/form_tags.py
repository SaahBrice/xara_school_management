from django import template
import re

register = template.Library()



@register.filter(name='addclass')
def addclass(value, arg):
    return value.as_widget(attrs={'class': arg})


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

