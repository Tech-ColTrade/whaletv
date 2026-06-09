from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


class UserManager(BaseUserManager):
    """Manager para el modelo de usuario que usa el correo como identificador."""

    use_in_migrations = True

    def _create_user(self, email, nombre, password, **extra_fields):
        if not email:
            raise ValueError('El correo es obligatorio')
        email = self.normalize_email(email)
        user = self.model(email=email, nombre=nombre, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, nombre, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, nombre, password, **extra_fields)

    def create_superuser(self, email, nombre, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self._create_user(email, nombre, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Usuario que inicia sesión con su correo y contraseña."""

    email = models.EmailField('correo', unique=True)
    nombre = models.CharField('nombre', max_length=150)

    is_active = models.BooleanField('activo', default=True)
    is_staff = models.BooleanField('es staff', default=False)
    date_joined = models.DateTimeField('fecha de registro', auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre']

    class Meta:
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def __str__(self):
        return f'{self.nombre} ({self.email})'
