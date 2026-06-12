from django.contrib import admin

from .models import Factura, RegistroSync, SyncJob, SyncJobItem, Televisor


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


class FacturaInline(admin.TabularInline):
    model = Factura
    extra = 0


@admin.register(Televisor)
class TelevisorAdmin(admin.ModelAdmin):
    list_display = (
        'mac_address',
        'serial_number',
        'nombre_persona',
        'correo_persona',
        'numero_cuotas',
        'lock_status',
    )
    list_filter = ('lock_status',)
    search_fields = ('mac_address', 'serial_number', 'nombre_persona', 'correo_persona')
    ordering = ('-created_at',)
    readonly_fields = ('lock_status',)
    inlines = [FacturaInline]


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = (
        'numero_factura',
        'televisor',
        'numero_cuota',
        'fecha_vencimiento',
        'pagada',
        'vencida',
    )
    list_filter = ('pagada',)
    search_fields = ('numero_factura', 'televisor__mac_address')
    ordering = ('televisor', 'numero_cuota')

    @admin.display(boolean=True, description='Vencida')
    def vencida(self, obj):
        return obj.vencida
