from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal

User = get_user_model()

class TailwindFormMixin:
    """Helper mixin to inject standard Tailwind styling into form widgets."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # Add classes for a premium input feel
            field.widget.attrs.update({
                'class': (
                    'mt-1 block w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl '
                    'text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 '
                    'focus:border-blue-500 transition duration-150 ease-in-out sm:text-sm'
                )
            })


class RegistrationForm(TailwindFormMixin, forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}),
        min_length=8,
        help_text='At least 8 characters long.'
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••'}),
        label='Confirm Password'
    )

    class Meta:
        model = User
        fields = ['email', 'name', 'age', 'height_cm', 'weight_kg', 'goal']
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'email@example.com'}),
            'name': forms.TextInput(attrs={'placeholder': 'John Doe'}),
            'age': forms.NumberInput(attrs={'placeholder': '25'}),
            'height_cm': forms.NumberInput(attrs={'placeholder': '175.5'}),
            'weight_kg': forms.NumberInput(attrs={'placeholder': '70.0'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('A user with this email address already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', 'Passwords do not match.')

        age = cleaned_data.get('age')
        if age is not None and age <= 0:
            self.add_error('age', 'Age must be a positive integer.')

        height = cleaned_data.get('height_cm')
        if height is not None and height <= Decimal('0.0'):
            self.add_error('height_cm', 'Height must be a positive decimal.')

        weight = cleaned_data.get('weight_kg')
        if weight is not None and weight <= Decimal('0.0'):
            self.add_error('weight_kg', 'Weight must be a positive decimal.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        # The ModelForm save path bypasses UserManager.create_user(), so the
        # username-defaults-to-email logic there never runs. Set it explicitly
        # here too, otherwise every user gets username='' and the second
        # registration collides on that empty string being already taken.
        if not user.username:
            user.username = user.email
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': (
                'mt-1 block w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl '
                'text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 '
                'focus:border-blue-500 transition duration-150 ease-in-out sm:text-sm'
            ),
            'placeholder': 'email@example.com'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': (
                'mt-1 block w-full px-4 py-2.5 bg-white border border-gray-300 rounded-xl '
                'text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 '
                'focus:border-blue-500 transition duration-150 ease-in-out sm:text-sm'
            ),
            'placeholder': '••••••••'
        })
    )


class ProfileForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'age', 'height_cm', 'weight_kg', 'goal']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'John Doe'}),
            'age': forms.NumberInput(attrs={'placeholder': '25'}),
            'height_cm': forms.NumberInput(attrs={'placeholder': '175.5'}),
            'weight_kg': forms.NumberInput(attrs={'placeholder': '70.0'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        age = cleaned_data.get('age')
        if age is not None and age <= 0:
            self.add_error('age', 'Age must be a positive integer.')

        height = cleaned_data.get('height_cm')
        if height is not None and height <= Decimal('0.0'):
            self.add_error('height_cm', 'Height must be a positive decimal.')

        weight = cleaned_data.get('weight_kg')
        if weight is not None and weight <= Decimal('0.0'):
            self.add_error('weight_kg', 'Weight must be a positive decimal.')

        return cleaned_data
