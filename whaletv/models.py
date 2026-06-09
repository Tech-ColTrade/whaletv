from django.db import models
from django.utils import timezone


class Televisor(models.Model):
    """Televisor WhaleTV: una compra a cuotas, con varias facturas."""

    mac_address = models.CharField('Mac Address', max_length=50)
    serial_number = models.CharField('Serial Number', max_length=50)

    numero_cuotas = models.PositiveIntegerField('Número de cuotas', default=0)

    # lock_status se calcula a partir de las facturas (ver calcular_estado()).
    lock_status = models.BooleanField('Lock Status', default=False)

    correo_persona = models.EmailField('Correo persona', max_length=254)
    nombre_persona = models.CharField('Nombre persona', max_length=150)

    created_at = models.DateTimeField('Fecha de registro', auto_now_add=True)

    class Meta:
        verbose_name = 'televisor'
        verbose_name_plural = 'televisores'

    def __str__(self):
        return f'{self.nombre_persona} - {self.mac_address}'

    # ------------------------------------------------------------------
    # Estado derivado de las facturas
    # ------------------------------------------------------------------
    def calcular_estado(self):
        """lock_status = hay alguna factura vencida (fecha < hoy) sin pagar.

        Aunque el cliente haya pagado cuotas posteriores, si quedó una
        cuota anterior vencida sin pagar, el TV sigue bloqueado.
        Devuelve True si lock_status cambió.
        """
        if not self.pk:
            return False
        hoy = timezone.localdate()
        vencida = self.facturas.filter(
            pagada=False, fecha_vencimiento__lt=hoy
        ).exists()
        cambio = self.lock_status != vencida
        self.lock_status = vencida
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
    def factura_pendiente(self):
        """La factura sin pagar más antigua (la deuda a cobrar)."""
        return self.facturas.filter(pagada=False).order_by('fecha_vencimiento').first()

    @property
    def fecha_sincronizar(self):
        """Fecha que se empuja al portal (la cuota pendiente más antigua)."""
        f = self.factura_pendiente
        return f.fecha_vencimiento if f else None

    @property
    def due_status(self):
        """Vencida = igual que bloqueado (hay cuota vencida sin pagar)."""
        return self.lock_status

    @property
    def cuotas_pagadas(self):
        return self.facturas.filter(pagada=True).count()

    @property
    def total_facturas(self):
        return self.facturas.count()


class Factura(models.Model):
    """Cada cuota del televisor es una factura con su fecha de vencimiento."""

    televisor = models.ForeignKey(
        Televisor,
        related_name='facturas',
        on_delete=models.CASCADE,
        verbose_name='televisor',
    )
    numero_factura = models.CharField('Número de factura', max_length=50)
    numero_cuota = models.PositiveIntegerField('Número de cuota', default=1)
    fecha_vencimiento = models.DateField('Fecha de vencimiento')
    pagada = models.BooleanField('Pagada', default=False)
    created_at = models.DateTimeField('Fecha de registro', auto_now_add=True)

    class Meta:
        verbose_name = 'factura'
        verbose_name_plural = 'facturas'
        ordering = ['numero_cuota', 'fecha_vencimiento']

    def __str__(self):
        return f'{self.numero_factura} (cuota {self.numero_cuota})'

    @property
    def vencida(self):
        return (not self.pagada) and self.fecha_vencimiento < timezone.localdate()

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
    ]
    estado = models.CharField(max_length=12, choices=ESTADOS, default='pendiente')
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
    mensaje = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return f'{self.mac} ({self.estado})'
