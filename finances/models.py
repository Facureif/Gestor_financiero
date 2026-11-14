from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import User


class Cliente(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    nombre = models.CharField(max_length=200, verbose_name='Nombre/Razón Social')
    slug = models.SlugField(max_length=220, blank=True, verbose_name='Slug URL')
    nombre_contacto = models.CharField(max_length=200, blank=True, verbose_name='Persona de contacto')
    email = models.EmailField(blank=True, verbose_name='Email')
    telefono = models.CharField(max_length=50, blank=True, verbose_name='Teléfono')
    direccion = models.CharField(max_length=300, blank=True, verbose_name='Dirección')
    ciudad = models.CharField(max_length=100, blank=True, verbose_name='Ciudad')
    provincia = models.CharField(max_length=100, blank=True, verbose_name='Provincia')
    cuit = models.CharField(max_length=20, blank=True, verbose_name='CUIT/CUIL')
    sistema = models.CharField(max_length=200, blank=True, verbose_name='Sistema contratado')
    plan = models.CharField(max_length=100, blank=True, verbose_name='Plan')
    fecha_inicio = models.DateField(null=True, blank=True, verbose_name='Cliente desde')
    notas = models.TextField(blank=True, verbose_name='Notas')
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'slug'],
                name='unique_slug_por_usuario'
            )
        ]
        indexes = [                                      # ← NUEVO
            models.Index(fields=['usuario', 'nombre']),
            models.Index(fields=['usuario', 'activo']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.nombre)[:200] or 'cliente'
            slug = base
            contador = 1
            while Cliente.objects.filter(
                usuario=self.usuario, slug=slug
            ).exclude(pk=self.pk).exists():
                slug = f"{base}-{contador}"
                contador += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    TIPO_CHOICES = [
        ('ingreso', 'Ingreso'),
        ('gasto', 'Gasto'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    icono = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default='#3498db')
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        unique_together = ['usuario', 'nombre']
        indexes = [                                      # ← NUEVO
            models.Index(fields=['usuario', 'tipo', 'activo']),
        ]

    def __str__(self):
        return f"{self.icono} {self.nombre}" if self.icono else self.nombre


class Cobro(models.Model):
    """Cobranzas - Dinero que te deben pagar"""
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagado', 'Pagado'),
        ('parcial', 'Pago Parcial'),
        ('vencido', 'Vencido'),
        ('cancelado', 'Cancelado'),
    ]

    FORMA_PAGO_CHOICES = [
        ('transferencia', 'Transferencia'),
        ('efectivo', 'Efectivo'),
        ('cheque', 'Cheque'),
        ('debito_automatico', 'Débito Automático'),
        ('otro', 'Otro'),
    ]

    PERIODICIDAD_CHOICES = [
        ('unico', 'Único'),
        ('semanal', 'Semanal'),
        ('quincenal', 'Quincenal'),
        ('mensual', 'Mensual'),
        ('bimestral', 'Bimestral'),
        ('trimestral', 'Trimestral'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    # Datos del cliente
    nombre_cliente = models.CharField(max_length=200, verbose_name='Cliente/Empresa')
    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Cliente (opcional)', related_name='cobros'
    )
    sistema = models.CharField(max_length=200, blank=True, verbose_name='Sistema',
                               help_text='Ej: Sistema de Concesionaria')
    plan = models.CharField(max_length=100, blank=True, verbose_name='Plan',
                            help_text='Ej: Básico, Premium')

    # Montos
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto a cobrar')
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Monto pagado')
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Saldo pendiente')

    # Fechas
    fecha_emision = models.DateField(default=timezone.now, verbose_name='Fecha de emisión')
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name='Fecha de vencimiento', db_index=True)
    fecha_pago = models.DateField(null=True, blank=True, verbose_name='Fecha de pago')

    # Estado
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES,
        default='pendiente', db_index=True         
    )
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default='transferencia')

    # Comprobante
    comprobante = models.FileField(
        upload_to='comprobantes/%Y/%m/', null=True, blank=True,
        verbose_name='Comprobante'
    )

    # Recurrencia
    es_recurrente = models.BooleanField(default=True, verbose_name='Es recurrente')
    periodicidad = models.CharField(max_length=20, choices=PERIODICIDAD_CHOICES, default='mensual')

    # Notas
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    meses_a_generar = models.IntegerField(
        default=1, verbose_name='Meses a generar',
        help_text='Cantidad de meses a generar por adelantado'
    )
    ajuste_precio_cada = models.IntegerField(
        default=0, verbose_name='Ajuste de precio cada N meses',
        help_text='0 = sin ajuste, 3 = cada 3 meses'
    )
    porcentaje_ajuste = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name='% de ajuste',
        help_text='Porcentaje de aumento (ej: 10 para 10%)'
    )
    concepto = models.CharField(max_length=200, blank=True, verbose_name='Concepto',
                               help_text='Ej: Desarrollo Web, Consultoría, Alquiler')
    detalle = models.CharField(max_length=100, blank=True, verbose_name='Detalle',
                            help_text='Ej: Pago mensual, Seña')
                            
    class Meta:
        ordering = ['-fecha_vencimiento']
        verbose_name = 'Cobro'
        verbose_name_plural = 'Cobros'
        indexes = [                                      # ← NUEVO
            models.Index(fields=['usuario', 'estado']),
            models.Index(fields=['usuario', 'fecha_vencimiento']),
            models.Index(fields=['usuario', 'cliente']),
        ]

    def __str__(self):                                   # ← FIX
        if self.monto_total is not None:
            return f"{self.nombre_cliente} - ${self.monto_total:,.2f}"
        return self.nombre_cliente

    def save(self, *args, **kwargs):
        # Asegurar que los valores no sean None
        if self.monto_total is None:
            self.monto_total = Decimal('0.00')
        if self.monto_pagado is None:
            self.monto_pagado = Decimal('0.00')
        if self.meses_a_generar is None:
            self.meses_a_generar = 1
        if self.ajuste_precio_cada is None:
            self.ajuste_precio_cada = 0
        if self.porcentaje_ajuste is None:
            self.porcentaje_ajuste = Decimal('0.00')

        # Calcular saldo usando Decimal (NO float)
        self.saldo = self.monto_total - self.monto_pagado

        # Actualizar estado
        if self.saldo <= 0:
            self.estado = 'pagado'
            self.saldo = Decimal('0.00')
        elif self.monto_pagado > 0 and self.saldo > 0:
            self.estado = 'parcial'

        hoy = timezone.localtime(timezone.now()).date()
        if (self.fecha_vencimiento 
                and self.fecha_vencimiento < hoy 
                and self.estado in ['pendiente', 'parcial']):
            self.estado = 'vencido'

        super().save(*args, **kwargs)

    @property
    def es_futuro(self):
        if not self.fecha_vencimiento:
            return False
        return self.fecha_vencimiento > timezone.localtime(timezone.now()).date()

        
    @property
    def dias_para_vencimiento(self):
        if self.estado in ['pagado', 'cancelado'] or not self.fecha_vencimiento:
            return None
        hoy = timezone.localtime(timezone.now()).date()
        delta = self.fecha_vencimiento - hoy
        return delta.days

    @property
    def porcentaje_pagado(self):
        if self.monto_total and self.monto_total > 0:
            return (self.monto_pagado / self.monto_total) * 100
        return 0


class Gasto(models.Model):
    FORMA_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta_credito', 'Tarjeta de Crédito'),
        ('tarjeta_debito', 'Tarjeta de Débito'),
        ('debito_automatico', 'Débito Automático'),
        ('cheque', 'Cheque'),
        ('otro', 'Otro'),
    ]

    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagado', 'Pagado'),
        ('vencido', 'Vencido'),
        ('cancelado', 'Cancelado'),
    ]

    PERIODICIDAD_CHOICES = [
        ('unico', 'Único'),
        ('mensual', 'Mensual'),
        ('bimestral', 'Bimestral'),
        ('trimestral', 'Trimestral'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
    ]

    TIPO_CHOICES = [
        ('fijo', 'Fijo'),
        ('servicio', 'Servicio'),
        ('impuesto', 'Impuesto'),
        ('variable', 'Variable'),
        ('otro', 'Otro'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tipo_gasto = models.CharField(max_length=20, choices=TIPO_CHOICES, default='fijo')
    fecha = models.DateField(default=timezone.now, db_index=True)                    # ← NUEVO
    fecha_vencimiento = models.DateField(null=True, blank=True, db_index=True)       # ← NUEVO
    fecha_pago = models.DateField(null=True, blank=True)
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default='efectivo')
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES,
        default='pendiente', db_index=True            # ← NUEVO
    )
    comprobante = models.FileField(upload_to='comprobantes/%Y/%m/', null=True, blank=True)
    es_recurrente = models.BooleanField(default=False)
    pago_automatico = models.BooleanField(default=False)
    periodicidad = models.CharField(max_length=20, choices=PERIODICIDAD_CHOICES, default='unico')
    meses_a_generar = models.IntegerField(default=1)
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Gasto'
        verbose_name_plural = 'Gastos'
        indexes = [                                      # ← NUEVO
            models.Index(fields=['usuario', 'estado']),
            models.Index(fields=['usuario', 'fecha']),
            models.Index(fields=['usuario', 'fecha_vencimiento']),
        ]

    def __str__(self):
        return f"{self.nombre} - ${self.monto:,.2f}" if self.monto else self.nombre

    @property
    def dias_para_vencimiento(self):
        if self.estado == 'pagado':
            return None
        if self.fecha_vencimiento:
            hoy = timezone.localtime(timezone.now()).date()
            delta = self.fecha_vencimiento - hoy
            return delta.days
        return None


class Notificacion(models.Model):
    TIPO_CHOICES = [
        ('cobro_vencido', 'Cobro vencido'),
        ('cobro_proximo', 'Cobro próximo'),
        ('pago_recibido', 'Pago recibido'),
        ('gasto_vencido', 'Gasto vencido'),
        ('recordatorio', 'Recordatorio'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False, db_index=True)    # ← NUEVO
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    cobro = models.ForeignKey(Cobro, on_delete=models.CASCADE, null=True, blank=True)
    gasto = models.ForeignKey(Gasto, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.titulo}"
    



class ItemCobro(models.Model):
    cobro = models.ForeignKey(Cobro, related_name='items', on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=200)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    
    def subtotal(self):
        return self.cantidad * self.precio_unitario

class ItemGasto(models.Model):
    gasto = models.ForeignKey(Gasto, related_name='items', on_delete=models.CASCADE)
    descripcion = models.CharField(max_length=200)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    
    def subtotal(self):
        return self.cantidad * self.precio_unitario



