from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'nombre')


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('email', 'nombre')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User

    list_display = ('email', 'nombre', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('email', 'nombre')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'nombre', 'password')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'password1', 'password2'),
        }),
    )
    readonly_fields = ('last_login', 'date_joined')
