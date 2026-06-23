from django.contrib import admin

from .models import Inhabilitacion, RegistroSync, SyncJob, SyncJobItem, Televisor


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'estado', 'usuario_email', 'total', 'workers', 'creado', 'terminado')
    list_filter = ('estado',)
    ordering = ('-creado',)


@admin.register(RegistroSync)
class RegistroSyncAdmin(admin.ModelAdmin):
    list_display = (
        'creado', 'usuario_email', 'nombre_persona', 'mac_address',
        'inhabilitado', 'aplicado', 'tipo',
    )
    list_filter = ('tipo', 'inhabilitado', 'aplicado')
    search_fields = ('mac_address', 'nombre_persona', 'usuario_email')
    ordering = ('-creado',)


class InhabilitacionInline(admin.TabularInline):
    model = Inhabilitacion
    extra = 0


@admin.register(Televisor)
class TelevisorAdmin(admin.ModelAdmin):
    list_display = (
        'mac_address',
        'serial_number',
        'numero_credito',
        'inhabilitado',
    )
    list_filter = ('inhabilitado',)
    search_fields = ('mac_address', 'serial_number', 'numero_credito')
    ordering = ('-created_at',)
    readonly_fields = ('inhabilitado',)
    inlines = [InhabilitacionInline]


@admin.register(Inhabilitacion)
class InhabilitacionAdmin(admin.ModelAdmin):
    list_display = (
        'mac_address',
        'serial_number',
        'estado',
        'televisor',
        'created_at',
    )
    list_filter = ('estado',)
    search_fields = ('mac_address', 'serial_number', 'televisor__mac_address')
    ordering = ('-created_at',)
