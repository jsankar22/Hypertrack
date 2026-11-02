from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

class AccountsAuthTests(TestCase):
    def setUp(self):
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.dashboard_url = reverse('dashboard')
        self.profile_url = reverse('profile')

        self.user_data = {
            'email': 'test@example.com',
            'name': 'Test User',
            'password': 'strongpassword123',
            'password_confirm': 'strongpassword123',
            'age': 25,
            'height_cm': Decimal('175.50'),
            'weight_kg': Decimal('70.00'),
            'goal': 'maintain'
        }

    def test_registration_view_get(self):
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')

    def test_registration_success(self):
        response = self.client.post(self.register_url, self.user_data)
        self.assertRedirects(response, self.dashboard_url)
        self.assertTrue(User.objects.filter(email='test@example.com').exists())

    def test_registration_validation_errors(self):
        # Passwords mismatch
        bad_data = self.user_data.copy()
        bad_data['password_confirm'] = 'different'
        response = self.client.post(self.register_url, bad_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'password_confirm', 'Passwords do not match.')

        # Invalid metrics
        bad_data = self.user_data.copy()
        bad_data['age'] = -5
        bad_data['weight_kg'] = -70.0
        response = self.client.post(self.register_url, bad_data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_login_success(self):
        user = User.objects.create_user(
            email='user@example.com',
            password='password123',
            name='Regular User'
        )
        response = self.client.post(self.login_url, {
            'email': 'user@example.com',
            'password': 'password123'
        })
        self.assertRedirects(response, self.dashboard_url)

    def test_login_failure(self):
        response = self.client.post(self.login_url, {
            'email': 'nonexistent@example.com',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")

    def test_logout(self):
        user = User.objects.create_user(
            email='user@example.com',
            password='password123'
        )
        self.client.login(email='user@example.com', password='password123')
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, self.login_url)

    def test_dashboard_login_required(self):
        response = self.client.get(self.dashboard_url)
        self.assertRedirects(response, f"{self.login_url}?next={self.dashboard_url}")

    def test_dashboard_success(self):
        user = User.objects.create_user(
            email='user@example.com',
            password='password123',
            name='Test User'
        )
        self.client.login(email='user@example.com', password='password123')
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test User")

    def test_profile_update(self):
        user = User.objects.create_user(
            email='user@example.com',
            password='password123',
            name='Old Name',
            age=20,
            weight_kg=Decimal('60.00'),
            height_cm=Decimal('160.00'),
            goal='lose_weight'
        )
        self.client.login(email='user@example.com', password='password123')
        
        # Perform edit
        response = self.client.post(self.profile_url, {
            'name': 'New Name',
            'age': 21,
            'weight_kg': Decimal('62.50'),
            'height_cm': Decimal('160.00'),
            'goal': 'maintain'
        })
        self.assertRedirects(response, self.dashboard_url)
        
        user.refresh_from_db()
        self.assertEqual(user.name, 'New Name')
        self.assertEqual(user.age, 21)
        self.assertEqual(user.weight_kg, Decimal('62.50'))
        self.assertEqual(user.goal, 'maintain')
