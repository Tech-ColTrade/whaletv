import datetime

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# Días que se suman/restan a la fecha de hoy al sincronizar con el portal.
DIAS_DESFASE = 30

# Un número de crédito: solo dígitos, hasta 60 (se guarda como texto porque
# 60 dígitos no caben en ningún entero de base de datos).
validar_numero_credito = RegexValidator(
    r'^\d{1,60}$',
    'El número de crédito debe contener solo dígitos (máximo 60).',
)


class Televisor(models.Model):
    """Televisor WhaleTV: se bloquea/desbloquea según su último Bloqueo."""

    mac_address = models.CharField('Dirección MAC', max_length=50)
    serial_number = models.CharField('Número de serie', max_length=50)
    numero_credito = models.CharField(
        'Número de crédito',
        max_length=60,
        blank=True,
        default='',
        validators=[validar_numero_credito],
    )

    # lock_status se calcula a partir de los bloqueos (ver calcular_estado()).
    lock_status = models.BooleanField('Lock Status', default=False)

    created_at = models.DateTimeField('Fecha de registro', auto_now_add=True)

    class Meta:
        verbose_name = 'televisor'
        verbose_name_plural = 'televisores'

    def __str__(self):
        return self.mac_address

    # ------------------------------------------------------------------
    # Estado derivado de los bloqueos
    # ------------------------------------------------------------------
    def calcular_estado(self):
        """lock_status = estado del último bloqueo registrado para el TV.

        Devuelve True si lock_status cambió.
        """
        if not self.pk:
            return False
        ultimo = self.bloqueos.first()  # ordenados por -created_at
        nuevo = bool(ultimo.estado) if ultimo else False
        cambio = self.lock_status != nuevo
        self.lock_status = nuevo
        return cambio

    def actualizar_lock(self):
        """Recalcula y persiste lock_status sin reentrar a save()."""
        if self.calcular_estado():
            Televisor.objects.filter(pk=self.pk).update(lock_status=self.lock_status)

    def save(self, *args, **kwargs):
        if self.pk:
            self.calcular_estado()
        super().save(*args, **kwargs)

    @classmethod
    def refrescar_todos(cls):
        for tv in cls.objects.all():
            tv.actualizar_lock()

    @property
    def fecha_sincronizar(self):
        """Fecha que se empuja al portal (Next Installment Date).

        - Bloqueado    → hoy − 30 días (fecha vencida → el portal lo bloquea).
        - Desbloqueado → hoy + 30 días (fecha futura → el portal lo deja libre).
        """
        hoy = timezone.localdate()
        dias = datetime.timedelta(days=DIAS_DESFASE)
        return hoy - dias if self.lock_status else hoy + dias

    @property
    def ultimo_bloqueo(self):
        """El bloqueo más reciente del televisor (define su estado actual)."""
        return self.bloqueos.first()


class Bloqueo(models.Model):
    """Estado de bloqueo de un televisor, cargado desde el Excel de bloqueos.

    Cada importación registra el estado (bloqueado/desbloqueado) de un TV.
    El estado actual del televisor (lock_status) es el del último bloqueo.
    """

    televisor = models.ForeignKey(
        Televisor,
        related_name='bloqueos',
        on_delete=models.CASCADE,
        verbose_name='televisor',
    )
    serial_number = models.CharField('Serial Number', max_length=50, blank=True, default='')
    mac_address = models.CharField('Mac Address', max_length=50)
    estado = models.BooleanField('Bloqueado', default=False)
    created_at = models.DateTimeField('Fecha de registro', auto_now_add=True)

    class Meta:
        verbose_name = 'bloqueo'
        verbose_name_plural = 'bloqueos'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.mac_address} · {"Bloqueado" if self.estado else "Desbloqueado"}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.televisor.actualizar_lock()

    def delete(self, *args, **kwargs):
        tv = self.televisor
        super().delete(*args, **kwargs)
        tv.actualizar_lock()


class SyncJob(models.Model):
    """Un trabajo de sincronización masiva con el portal (corre en segundo plano)."""

    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('corriendo', 'Corriendo'),
        ('terminado', 'Terminado'),
        ('error', 'Error'),
        ('cancelado', 'Cancelado'),
    ]
    # Estados que cuentan como "todavía trabajando" (bloquean lanzar otro job).
    ACTIVOS = ('pendiente', 'corriendo')

    TIPOS = [('sincronizacion', 'Sincronización'), ('validacion', 'Validación')]
    tipo = models.CharField(max_length=14, choices=TIPOS, default='sincronizacion')

    estado = models.CharField(max_length=12, choices=ESTADOS, default='pendiente')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='sync_jobs',
        verbose_name='usuario',
    )
    usuario_email = models.CharField(
        'Correo de quien sincronizó', max_length=254, blank=True, default=''
    )
    total = models.PositiveIntegerField(default=0)
    workers = models.PositiveIntegerField(default=4)
    error = models.TextField(blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    terminado = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'sincronización'
        verbose_name_plural = 'sincronizaciones'
        ordering = ['-creado']

    def __str__(self):
        return f'Sync #{self.pk} ({self.estado})'


class SyncJobItem(models.Model):
    """Resultado de sincronizar un televisor dentro de un SyncJob."""

    ESTADOS = [('pendiente', 'Pendiente'), ('ok', 'OK'), ('error', 'Error')]

    job = models.ForeignKey(SyncJob, related_name='items', on_delete=models.CASCADE)
    televisor = models.ForeignKey(
        Televisor, null=True, blank=True, on_delete=models.SET_NULL
    )
    mac = models.CharField(max_length=50)
    estado = models.CharField(max_length=10, choices=ESTADOS, default='pendiente')
    aplicado = models.BooleanField(default=False)
    # Para trabajos de validación (dry-run): estado leído en el portal, estado
    # local de la app, y si coinciden.
    remoto_bloqueado = models.BooleanField(null=True, blank=True)
    local_bloqueado = models.BooleanField(null=True, blank=True)
    coincide = models.BooleanField(null=True, blank=True)
    mensaje = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return f'{self.mac} ({self.estado})'


class RegistroSync(models.Model):
    """Bitácora: quién sincronizó qué televisor (nombre + MAC) y cuándo."""

    TIPOS = [('individual', 'Individual'), ('masivo', 'Masivo')]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='registros_sync',
        verbose_name='quién sincronizó',
    )
    # Copias planas por si luego borran el usuario o el televisor.
    usuario_email = models.CharField('Correo', max_length=254, blank=True, default='')
    televisor = models.ForeignKey(
        Televisor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='registros_sync',
        verbose_name='televisor',
    )
    nombre_persona = models.CharField('Nombre persona', max_length=150, blank=True, default='')
    mac_address = models.CharField('Mac Address', max_length=50)
    lock_status = models.BooleanField('Quedó bloqueado', default=False)
    aplicado = models.BooleanField('Aplicó cambio en el portal', default=False)
    tipo = models.CharField(max_length=12, choices=TIPOS, default='individual')
    creado = models.DateTimeField('Fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'registro de sincronización'
        verbose_name_plural = 'registros de sincronización'
        ordering = ['-creado']

    def __str__(self):
        return f'{self.usuario_email} → {self.mac_address} ({self.creado:%d/%m/%Y %H:%M})'

    @classmethod
    def registrar(cls, usuario, televisor, *, aplicado, tipo):
        """Crea un registro tomando una foto del usuario y del televisor."""
        return cls.objects.create(
            usuario=usuario if getattr(usuario, 'pk', None) else None,
            usuario_email=getattr(usuario, 'email', '') or '',
            televisor=televisor,
            mac_address=televisor.mac_address,
            lock_status=bool(televisor.lock_status),
            aplicado=bool(aplicado),
            tipo=tipo,
        )


class PinCodeGenerado(models.Model):
    """Bitácora de cada Pin Code generado (Desbloquear Manual): MAC + Passcode + Pin."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='pincodes',
        verbose_name='quién lo generó',
    )
    usuario_email = models.CharField('Correo', max_length=254, blank=True, default='')
    mac_address = models.CharField('Mac Address', max_length=50)
    passcode = models.CharField('Passcode', max_length=100)
    pin_code = models.CharField('Pin Code', max_length=100)
    creado = models.DateTimeField('Fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'pin code generado'
        verbose_name_plural = 'pin codes generados'
        ordering = ['-creado']

    def __str__(self):
        return f'{self.mac_address} → {self.pin_code} ({self.creado:%d/%m/%Y %H:%M})'
