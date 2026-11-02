"""Deterministic nutrition maths.

LLMs are unreliable at arithmetic, so the chatbot calls this function as a
tool instead of computing calorie/macro numbers itself.

BMR uses the Mifflin-St Jeor equation (Mifflin et al., 1990).
"""

ACTIVITY_MULTIPLIERS = {
    'sedentary': 1.2,        # desk job, little or no exercise
    'light': 1.375,          # light exercise 1-3 days/week
    'moderate': 1.55,        # moderate exercise 3-5 days/week
    'very_active': 1.725,    # hard exercise 6-7 days/week
    'extra_active': 1.9,     # very hard exercise plus a physical job
}

# calorie adjustment vs maintenance, protein target in g per kg body weight
GOAL_SETTINGS = {
    'cut': {'adjustment': -0.20, 'protein_per_kg': 2.2},
    'maintain': {'adjustment': 0.0, 'protein_per_kg': 1.8},
    'bulk': {'adjustment': 0.10, 'protein_per_kg': 2.0},
}

GOAL_ALIASES = {
    'cut': 'cut', 'cutting': 'cut', 'lose_weight': 'cut', 'fat_loss': 'cut', 'lose': 'cut',
    'maintain': 'maintain', 'maintenance': 'maintain',
    'bulk': 'bulk', 'bulking': 'bulk', 'gain_muscle': 'bulk', 'gain': 'bulk',
}

CALORIE_FLOOR = {'male': 1500, 'female': 1200}


def calculate_nutrition_targets(weight_kg, height_cm, age, sex, activity_level, goal):
    """Return BMR, TDEE, a calorie target and macro targets in grams.

    On invalid input returns {'error': '...'} so the caller (the LLM) can relay it.
    """
    try:
        weight_kg = float(weight_kg)
        height_cm = float(height_cm)
        age = int(age)
    except (TypeError, ValueError):
        return {'error': 'weight_kg, height_cm and age must be numbers.'}

    sex = str(sex or '').strip().lower()
    activity_level = str(activity_level or '').strip().lower()
    goal = GOAL_ALIASES.get(str(goal or '').strip().lower())

    if sex not in ('male', 'female'):
        return {'error': "sex must be 'male' or 'female' (needed for the BMR equation). Ask the user."}
    if activity_level not in ACTIVITY_MULTIPLIERS:
        return {'error': f"activity_level must be one of {sorted(ACTIVITY_MULTIPLIERS)}. Ask the user."}
    if goal is None:
        return {'error': "goal must be one of 'cut', 'maintain' or 'bulk'."}
    if age < 18:
        return {'error': 'Adult calorie equations are not appropriate under 18. '
                         'Recommend speaking with a doctor or registered dietitian.'}
    if age > 100 or not (30 <= weight_kg <= 300) or not (120 <= height_cm <= 230):
        return {'error': 'Inputs are outside plausible ranges. Ask the user to confirm them.'}

    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == 'male' else -161)
    tdee = bmr * ACTIVITY_MULTIPLIERS[activity_level]
    settings_ = GOAL_SETTINGS[goal]
    target = tdee * (1 + settings_['adjustment'])

    notes = []
    floor = CALORIE_FLOOR[sex]
    if target < floor:
        target = floor
        notes.append(f'Target raised to the {floor} kcal safety floor; a larger deficit is not recommended '
                     'without medical supervision.')

    protein_g = settings_['protein_per_kg'] * weight_kg
    fat_g = max(0.25 * target / 9, 0.6 * weight_kg)
    carbs_g = max((target - protein_g * 4 - fat_g * 9) / 4, 0)

    if goal == 'cut':
        notes.append('Aim to lose roughly 0.5-1% of body weight per week; adjust if progress stalls for 2-3 weeks.')
    elif goal == 'bulk':
        notes.append('Aim to gain roughly 0.25-0.5% of body weight per week; adjust if progress stalls for 2-3 weeks.')
    notes.append('These are estimates. Track body weight for 2-3 weeks and adjust calories by 100-200 kcal as needed.')

    return {
        'goal': goal,
        'bmr_kcal': round(bmr),
        'maintenance_kcal': round(tdee),
        'target_kcal': round(target),
        'protein_g': round(protein_g),
        'carbs_g': round(carbs_g),
        'fat_g': round(fat_g),
        'protein_g_per_kg': settings_['protein_per_kg'],
        'notes': notes,
    }


# Tool definition shared by both LLM providers (JSON Schema).
NUTRITION_TOOL = {
    'name': 'calculate_nutrition_targets',
    'description': (
        'Calculate daily calorie and macronutrient (protein/carbs/fat in grams) targets for a user. '
        'ALWAYS use this for any calorie or macro numbers instead of calculating yourself. '
        'Only call it once you know all six inputs; ask the user for any that are missing.'
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'weight_kg': {'type': 'number', 'description': 'Body weight in kilograms'},
            'height_cm': {'type': 'number', 'description': 'Height in centimetres'},
            'age': {'type': 'integer', 'description': 'Age in years'},
            'sex': {'type': 'string', 'enum': ['male', 'female']},
            'activity_level': {
                'type': 'string',
                'enum': list(ACTIVITY_MULTIPLIERS),
                'description': 'sedentary, light (1-3 days/wk), moderate (3-5), very_active (6-7), extra_active',
            },
            'goal': {'type': 'string', 'enum': ['cut', 'maintain', 'bulk']},
        },
        'required': ['weight_kg', 'height_cm', 'age', 'sex', 'activity_level', 'goal'],
    },
}

TOOLS = [NUTRITION_TOOL]
TOOL_HANDLERS = {'calculate_nutrition_targets': calculate_nutrition_targets}
