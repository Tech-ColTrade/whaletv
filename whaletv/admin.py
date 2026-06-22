from django.contrib import admin

from .models import Bloqueo, RegistroSync, SyncJob, SyncJobItem, Televisor


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'estado', 'usuario_email', 'total', 'workers', 'creado', 'terminado')
    list_filter = ('estado',)
    ordering = ('-creado',)


@admin.register(RegistroSync)
class RegistroSyncAdmin(admin.ModelAdmin):
    list_display = (
        'creado', 'usuario_email', 'nombre_persona', 'mac_address',
        'lock_status', 'aplicado', 'tipo',
    )
    list_filter = ('tipo', 'lock_status', 'aplicado')
    search_fields = ('mac_address', 'nombre_persona', 'usuario_email')
    ordering = ('-creado',)


class BloqueoInline(admin.TabularInline):
    model = Bloqueo
    extra = 0


@admin.register(Televisor)
class TelevisorAdmin(admin.ModelAdmin):
    list_display = (
        'mac_address',
        'serial_number',
        'numero_credito',
        'lock_status',
    )
    list_filter = ('lock_status',)
    search_fields = ('mac_address', 'serial_number', 'numero_credito')
    ordering = ('-created_at',)
    readonly_fields = ('lock_status',)
    inlines = [BloqueoInline]


@admin.register(Bloqueo)
class BloqueoAdmin(admin.ModelAdmin):
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
