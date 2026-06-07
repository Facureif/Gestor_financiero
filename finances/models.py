from django.db import models
from django.utils import timezone
from django.db.models import Sum
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
import calendar
from django.contrib.auth.models import User



class Cliente(models.Model):
    """Ficha técnica de clientes (opcional)"""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    nombre = models.CharField(max_length=200, verbose_name='Nombre/Razón Social')
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
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, 
                           verbose_name='Cliente (opcional)', related_name='cobros')
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
    fecha_vencimiento = models.DateField(verbose_name='Fecha de vencimiento')
    fecha_pago = models.DateField(null=True, blank=True, verbose_name='Fecha de pago')
    
    # Estado
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default='transferencia')
    
    # Comprobante
    comprobante = models.FileField(upload_to='comprobantes/%Y/%m/', null=True, blank=True,
                                   verbose_name='Comprobante')
    
    # Recurrencia
    es_recurrente = models.BooleanField(default=True, verbose_name='Es recurrente')
    periodicidad = models.CharField(max_length=20, choices=PERIODICIDAD_CHOICES, default='mensual')
    
    # Notas
    observaciones = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    meses_a_generar = models.IntegerField(default=1, verbose_name='Meses a generar',
                                         help_text='Cantidad de meses a generar por adelantado')
    ajuste_precio_cada = models.IntegerField(default=0, verbose_name='Ajuste de precio cada N meses',
                                            help_text='0 = sin ajuste, 3 = cada 3 meses')
    porcentaje_ajuste = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                           verbose_name='% de ajuste',
                                           help_text='Porcentaje de aumento (ej: 10 para 10%)')
    
    class Meta:
        ordering = ['-fecha_vencimiento']
        verbose_name = 'Cobro'
        verbose_name_plural = 'Cobros'
    
    def __str__(self):
        return f"{self.nombre_cliente} - ${self.monto_total:,.2f}"
    
    def save(self, *args, **kwargs):
        # Asegurar que los valores no sean None
        if self.monto_total is None:
            self.monto_total = 0
        if self.monto_pagado is None:
            self.monto_pagado = 0
        if self.meses_a_generar is None:
            self.meses_a_generar = 1
        if self.ajuste_precio_cada is None:
            self.ajuste_precio_cada = 0
        if self.porcentaje_ajuste is None:
            self.porcentaje_ajuste = 0
        
        # Convertir a float
        monto_total = float(self.monto_total)
        monto_pagado = float(self.monto_pagado)
        
        # Calcular saldo
        self.saldo = monto_total - monto_pagado
        
        # Actualizar estado
        if self.saldo <= 0:
            self.estado = 'pagado'
            self.saldo = 0
        elif monto_pagado > 0 and self.saldo > 0:
            self.estado = 'parcial'
        
    
        from django.utils import timezone
        hoy = timezone.localtime(timezone.now()).date()
        if self.fecha_vencimiento and self.fecha_vencimiento < hoy and self.estado in ['pendiente', 'parcial']:
            self.estado = 'vencido'

        super().save(*args, **kwargs)
    
    @property
    def dias_para_vencimiento(self):
        if self.estado in ['pagado', 'cancelado']:
            return None
        from django.utils import timezone
        hoy = timezone.localtime(timezone.now()).date()  # CORREGIDO
        delta = self.fecha_vencimiento - hoy
        return delta.days
    
    @property
    def porcentaje_pagado(self):
        if self.monto_total > 0:
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
    fecha = models.DateField(default=timezone.now)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO_CHOICES, default='efectivo')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente')
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
    
    def __str__(self):
        return f"{self.nombre} - ${self.monto:,.2f}" if self.monto else f"{self.nombre}"
    
    @property
    def dias_para_vencimiento(self):
        if self.estado == 'pagado':
            return None
        if self.fecha_vencimiento:
            from django.utils import timezone
            hoy = timezone.localtime(timezone.now()).date()  # CORREGIDO
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
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    cobro = models.ForeignKey(Cobro, on_delete=models.CASCADE, null=True, blank=True)
    gasto = models.ForeignKey(Gasto, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
    
    def __str__(self):
        return f"{self.get_tipo_display()}: {self.titulo}"