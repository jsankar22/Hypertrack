from django import template

register = template.Library()

@register.simple_tag
def sum_calories(meals):
    """Calculate the total calories for a list of nutrition logs."""
    if not meals:
        return 0
    return sum(meal.calories for meal in meals)
