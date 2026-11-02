from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ['email', 'username', 'name', 'age', 'height_cm', 'weight_kg', 'goal', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Fitness Profiles', {'fields': ('name', 'age', 'height_cm', 'weight_kg', 'goal')}),
    )
    # Since AbstractUser requires username, we map username and email. Custom fields are added here.
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Fitness Profiles', {'fields': ('name', 'age', 'height_cm', 'weight_kg', 'goal')}),
    )

admin.site.register(User, CustomUserAdmin)
