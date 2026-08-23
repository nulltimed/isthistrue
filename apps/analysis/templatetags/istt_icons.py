"""4.2 H4/H9 (decision de David): TODOS los iconos pictograficos, sencillos y en
CONTORNO NEGRO. Un solo juego SVG inline (stroke=currentColor, fill=none) usable
en cualquier plantilla: {% load istt_icons %} ... {% icon 'bell' %}."""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

_P = {
    'bell': 'M6 8a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6M10 20a2 2 0 0 0 4 0',
    'bell_off': 'M6 8a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6M10 20a2 2 0 0 0 4 0M3 3l18 18',
    'mail': 'M4 5h16v14H4zM4 6l8 7 8-7',
    'eye': 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7zM12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0',
    'eye_off': 'M2 12s3.5-7 10-7c2 0 3.7.6 5.2 1.5M22 12s-3.5 7-10 7c-2 0-3.7-.6-5.2-1.5M9.9 9.9a3 3 0 0 0 4.2 4.2M3 3l18 18',
    'flag': 'M5 21V4m0 1h13l-2.5 4L18 13H5',
    'shield': 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
    'up': 'M12 19V5M5 12l7-7 7 7',
    'down': 'M12 5v14M5 12l7 7 7-7',
    'user': 'M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0M4 21c1.5-4 5-5 8-5s6.5 1 8 5',
    'users': 'M9 11m-3.5 0a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0-7 0M2 20c1-3.5 4-4.5 7-4.5s6 1 7 4.5M16 4a3.5 3.5 0 0 1 0 7M18 15.5c2 .6 3.4 1.8 4 4.5',
    'key': 'M14 10m-5 0a5 5 0 1 0 10 0a5 5 0 1 0-10 0M9 10L3 16v3h3l1.5-1.5V16H9l1.5-1.5',
    'image': 'M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M9 9.5m-1.2 0a1.2 1.2 0 1 0 2.4 0a1.2 1.2 0 1 0-2.4 0',
    'ticket': 'M4 8h16v3a2 2 0 0 0 0 4v3H4v-3a2 2 0 0 0 0-4zM13 8v10',
    'trash': 'M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13M10 11v5M14 11v5',
    'flame': 'M12 3s5 4.5 5 9a5 5 0 0 1-10 0c0-2 1-3.5 2-5 .4 1.4 1.2 2.2 2 2.5C10.5 7.5 11 5 12 3z',
    'chat': 'M4 5h16v11H9l-5 4z',
    'search': 'M10.5 10.5m-6.5 0a6.5 6.5 0 1 0 13 0a6.5 6.5 0 1 0-13 0M15.5 15.5L21 21',
    'sliders': 'M5 4v6M5 14v6M12 4v10M12 18v2M19 4v2M19 10v10M3 10h4M10 14h4M17 6h4',
    'gauge': 'M12 20a8 8 0 1 1 8-8M12 12l4-3',
    'globe': 'M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0M3 12h18M12 3c2.5 2.6 2.5 15.4 0 18'
             'M12 3c-2.5 2.6-2.5 15.4 0 18',
}


@register.simple_tag
def icon(name, size=18, cls=''):
    d = _P.get(name, _P['flag'])
    return mark_safe(
        f'<svg class="icon {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true"><path d="{d}"/></svg>')


@register.filter
def md(text):
    """Markdown con HTML ESCAPADO (mismo criterio que el foro machina): para los MP."""
    import markdown2
    return mark_safe(markdown2.markdown(str(text or ''), safe_mode='escape'))
