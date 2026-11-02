import requests
from django.conf import settings
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

FALLBACK_FOODS = [
    {"name": "Chicken Breast (100g)", "kcal_per_100g": 165, "protein": 31.0, "carbs": 0.0, "fats": 3.6},
    {"name": "Brown Rice (100g)", "kcal_per_100g": 111, "protein": 2.6, "carbs": 23.0, "fats": 0.9},
    {"name": "Whole Egg (100g)", "kcal_per_100g": 155, "protein": 13.0, "carbs": 1.1, "fats": 11.0},
    {"name": "Oatmeal (100g)", "kcal_per_100g": 389, "protein": 16.9, "carbs": 66.3, "fats": 6.9},
    {"name": "Banana (100g)", "kcal_per_100g": 89, "protein": 1.1, "carbs": 22.8, "fats": 0.3},
    {"name": "Peanut Butter (100g)", "kcal_per_100g": 588, "protein": 25.0, "carbs": 20.0, "fats": 50.0},
    {"name": "Whey Protein Powder (100g)", "kcal_per_100g": 400, "protein": 80.0, "carbs": 6.0, "fats": 6.0},
    {"name": "Greek Yogurt Plain (100g)", "kcal_per_100g": 59, "protein": 10.0, "carbs": 3.6, "fats": 0.4},
    {"name": "Salmon Fillet (100g)", "kcal_per_100g": 208, "protein": 20.0, "carbs": 0.0, "fats": 13.0},
    {"name": "Sweet Potato (100g)", "kcal_per_100g": 86, "protein": 1.6, "carbs": 20.0, "fats": 0.1},
    {"name": "Apple (100g)", "kcal_per_100g": 52, "protein": 0.3, "carbs": 14.0, "fats": 0.2},
    {"name": "Broccoli (100g)", "kcal_per_100g": 34, "protein": 2.8, "carbs": 7.0, "fats": 0.4},
]

def search_usda_foods(query):
    """
    Search USDA FoodData Central API for a given query.
    If the API call fails or the key is DEMO_KEY/empty, fall back to our high-quality local dataset.
    """
    if not query:
        return []

    api_key = getattr(settings, 'USDA_API_KEY', 'DEMO_KEY')
    
    # If using DEMO_KEY, let's check if we can query the public API, but keep fallback ready
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {
        'query': query,
        'api_key': api_key,
        'pageSize': 10
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            foods = data.get('foods', [])
            results = []
            for food in foods:
                name = food.get('description', 'Unknown Food')
                nutrients = food.get('foodNutrients', [])
                
                # Extract macronutrients (per 100g or unit)
                kcal = 0
                protein = Decimal('0.0')
                carbs = Decimal('0.0')
                fats = Decimal('0.0')
                
                for n in nutrients:
                    nutrient_id = n.get('nutrientId')
                    n_name = n.get('nutrientName', '').lower()
                    val = n.get('value', 0)
                    
                    if nutrient_id == 1008 or 'energy' in n_name or 'kcal' in n_name:
                        kcal = int(val)
                    elif nutrient_id == 1003 or 'protein' in n_name:
                        protein = Decimal(str(val))
                    elif nutrient_id == 1005 or 'carbohydrate' in n_name:
                        carbs = Decimal(str(val))
                    elif nutrient_id == 1004 or 'fat' in n_name or 'lipid' in n_name:
                        fats = Decimal(str(val))
                        
                results.append({
                    'name': name,
                    'kcal_per_100g': kcal,
                    'protein': float(protein),
                    'carbs': float(carbs),
                    'fats': float(fats)
                })
            
            # If we got valid results from USDA, return them
            if results:
                return results
    except Exception as e:
        logger.error(f"Error querying USDA API: {e}. Falling back to local data.")

    # Local Fallback Filtering
    query_lower = query.lower()
    local_results = [
        food for food in FALLBACK_FOODS
        if query_lower in food['name'].lower()
    ]
    
    # If no local results match the specific query, return a general selection
    if not local_results:
        return FALLBACK_FOODS[:5]
        
    return local_results
