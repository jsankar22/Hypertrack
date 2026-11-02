from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import NutritionLog
from unittest.mock import patch, MagicMock
from decimal import Decimal
import datetime

User = get_user_model()

class NutritionTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(email='user1@example.com', password='password123', weight_kg=Decimal('70.00'), goal='maintain')
        self.user2 = User.objects.create_user(email='user2@example.com', password='password123')
        
        self.daily_url = reverse('nutrition_daily')
        self.log_add_url = reverse('nutrition_log_add')
        
        # Log food for user1
        self.log1 = NutritionLog.objects.create(
            user=self.user1,
            food_name='Oatmeal',
            calories=389,
            protein_g=Decimal('16.90'),
            carbs_g=Decimal('66.30'),
            fats_g=Decimal('6.90'),
            meal_type='breakfast',
            date=datetime.date(2026, 6, 1)
        )

    def test_daily_view_login_required(self):
        response = self.client.get(self.daily_url)
        self.assertEqual(response.status_code, 302)

    def test_daily_view_totals_calc(self):
        self.client.login(email='user1@example.com', password='password123')
        response = self.client.get(self.daily_url + '?date=2026-06-01')
        self.assertEqual(response.status_code, 200)
        
        # Check totals in context
        self.assertEqual(response.context['total_calories'], 389)
        self.assertEqual(response.context['total_protein'], 16.90)
        self.assertEqual(response.context['total_carbs'], 66.30)
        self.assertEqual(response.context['total_fats'], 6.90)

    @patch('nutrition.services.requests.get')
    def test_nutrition_search_api_with_mocked_usda(self, mock_get):
        self.client.login(email='user1@example.com', password='password123')
        
        # Mock USDA response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_ok = True
        mock_response.json.return_value = {
            'foods': [
                {
                    'description': 'USDA Chicken Breast',
                    'foodNutrients': [
                        {'nutrientId': 1008, 'nutrientName': 'Energy', 'value': 165},
                        {'nutrientId': 1003, 'nutrientName': 'Protein', 'value': 31.0},
                        {'nutrientId': 1005, 'nutrientName': 'Carbohydrate, by difference', 'value': 0.0},
                        {'nutrientId': 1004, 'nutrientName': 'Total lipid (fat)', 'value': 3.6}
                    ]
                }
            ]
        }
        mock_get.return_value = mock_response
        
        search_url = reverse('nutrition_search_api') + '?q=chicken'
        response = self.client.get(search_url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'USDA Chicken Breast')
        self.assertEqual(data[0]['kcal_per_100g'], 165)
        self.assertEqual(data[0]['protein'], 31.0)

    def test_nutrition_log_create_scaled(self):
        self.client.login(email='user1@example.com', password='password123')
        
        # Log a 200g portion of Peanut Butter
        # Peanut Butter per 100g: 588 kcal, P: 25g, C: 20g, F: 50g
        # 200g scale: 1176 kcal, P: 50g, C: 40g, F: 100g
        response = self.client.post(self.log_add_url, {
            'food_name': 'Peanut Butter',
            'calories_per_100g': 588,
            'protein_per_100g': 25.0,
            'carbs_per_100g': 20.0,
            'fats_per_100g': 50.0,
            'portion_grams': 200.00,
            'meal_type': 'snack',
            'date': '2026-06-02'
        })
        
        self.assertRedirects(response, '/nutrition/?date=2026-06-02')
        
        log = NutritionLog.objects.get(food_name='Peanut Butter', user=self.user1)
        self.assertEqual(log.calories, 1176)
        self.assertEqual(log.protein_g, Decimal('50.00'))
        self.assertEqual(log.carbs_g, Decimal('40.00'))
        self.assertEqual(log.fats_g, Decimal('100.00'))

    def test_nutrition_delete_own_log(self):
        self.client.login(email='user1@example.com', password='password123')
        delete_url = reverse('nutrition_delete', args=[self.log1.id])
        
        response = self.client.post(delete_url)
        self.assertRedirects(response, '/nutrition/?date=2026-06-01')
        self.assertFalse(NutritionLog.objects.filter(id=self.log1.id).exists())

    def test_nutrition_delete_others_log_denied(self):
        self.client.login(email='user2@example.com', password='password123')
        delete_url = reverse('nutrition_delete', args=[self.log1.id])
        
        response = self.client.post(delete_url)
        # Trying to delete another user's log returns 404
        self.assertEqual(response.status_code, 404)
        self.assertTrue(NutritionLog.objects.filter(id=self.log1.id).exists())

    def test_nutrition_history_api(self):
        self.client.login(email='user1@example.com', password='password123')
        history_url = reverse('nutrition_history_api')
        
        response = self.client.get(history_url)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data), 7) # Should contain exactly 7 days
        # One of the dates matches log1 (2026-06-01)
        matching_day = [day for day in data if day['date'] == '2026-06-01']
        if matching_day:
            self.assertEqual(matching_day[0]['calories'], 389)
            self.assertEqual(matching_day[0]['protein'], 16.9)
