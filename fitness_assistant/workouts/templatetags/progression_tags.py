from django import template
from django.utils import timezone

from workouts.progression import get_progression_for_user

register = template.Library()


@register.inclusion_tag('workouts/_progression_card.html', takes_context=True)
def progression_card(context, limit=4):
    """Dashboard widget. Fails soft so it can never break the dashboard."""
    user = context.get('user') or getattr(context.get('request'), 'user', None)
    data = {'ready': False, 'message': '', 'items': []}
    if user is not None and getattr(user, 'is_authenticated', False):
        try:
            data = get_progression_for_user(user, today=timezone.localdate(), limit=limit)
        except Exception:
            data = {'ready': False, 'message': 'Progression is temporarily unavailable.', 'items': []}
    return {'prog': data}
