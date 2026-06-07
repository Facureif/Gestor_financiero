from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import Categoria, Cliente, Cobro, Gasto, Notificacion

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'color_preview', 'activo']
    list_filter = ['tipo', 'activo']
    search_fields = ['nombre']
    
    def color_preview(self, obj):
        return format_html(
            '<div style="background-color: {}; width: 20px; height: 20px; border-radius: 50%;"></div>',
            obj.color
        )
    color_preview.short_description = 'Color'

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'nombre_contacto', 'telefono', 'email', 'plan', 'activo']
    list_filter = ['activo', 'plan', 'provincia']
    search_fields = ['nombre', 'email', 'telefono', 'cuit']
    fieldsets = (
        ('Datos Principales', {
            'fields': ('nombre', 'nombre_contacto', 'email', 'telefono')
        }),
        ('Dirección', {
            'fields': ('direccion', 'ciudad', 'provincia')
        }),
        ('Información Fiscal', {
            'fields': ('cuit',)
        }),
        ('Servicio', {
            'fields': ('sistema', 'plan', 'fecha_inicio')
        }),
        ('Notas y Estado', {
            'fields': ('notas', 'activo')
        }),
    )

@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = ['nombre_cliente', 'cliente', 'plan', 'monto_total', 'monto_pagado', 'saldo', 
                   'estado_coloreado', 'fecha_vencimiento', 'meses_a_generar', 'dias_status']
    list_filter = ['estado', 'plan', 'es_recurrente', 'periodicidad']
    search_fields = ['nombre_cliente', 'sistema', 'cliente__nombre']
    date_hierarchy = 'fecha_vencimiento'
    readonly_fields = ['creado', 'actualizado']
    
    fieldsets = (
        ('Cliente', {
            'fields': ('cliente', 'nombre_cliente', 'sistema', 'plan')
        }),
        ('Montos', {
            'fields': ('monto_total', 'monto_pagado', 'saldo')
        }),
        ('Fechas', {
            'fields': ('fecha_emision', 'fecha_vencimiento', 'fecha_pago')
        }),
        ('Estado', {
            'fields': ('estado', 'forma_pago')
        }),
        ('Comprobante', {
            'fields': ('comprobante',)
        }),
        ('Recurrencia', {
            'fields': ('es_recurrente', 'periodicidad', 'meses_a_generar')
        }),
        ('Notas', {
            'fields': ('observaciones',)
        }),
        ('Metadata', {
            'fields': ('creado', 'actualizado'),
            'classes': ('collapse',)
        }),
    )
    
    def estado_coloreado(self, obj):
        colores = {'pendiente': 'orange', 'pagado': 'green', 'parcial': 'blue', 
                   'vencido': 'red', 'cancelado': 'gray'}
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>',
                          colores.get(obj.estado, 'black'), obj.get_estado_display())
    estado_coloreado.short_description = 'Estado'
    
    def dias_status(self, obj):
        dias = obj.dias_para_vencimiento
        if dias is not None:
            if dias < 0:
                return format_html('<span style="color: red;">⚠️ Vencido hace {} días</span>', abs(dias))
            elif dias == 0:
                return format_html('<span style="color: orange;">⚠️ Vence hoy</span>')
            elif dias <= 3:
                return format_html('<span style="color: orange;">⏰ {} días</span>', dias)
            else:
                return format_html('📅 {} días', dias)
        return '-'
    dias_status.short_description = 'Vencimiento'
    
    actions = ['registrar_pago_completo', 'marcar_como_vencido']
    
    def registrar_pago_completo(self, request, queryset):
        for cobro in queryset:
            cobro.monto_pagado = cobro.monto_total
            cobro.fecha_pago = timezone.now().date()
            cobro.save()
        self.message_user(request, f'{queryset.count()} cobros marcados como pagados.')
    registrar_pago_completo.short_description = "✅ Registrar pago completo"
    
    def marcar_como_vencido(self, request, queryset):
        queryset.update(estado='vencido')
        self.message_user(request, f'{queryset.count()} cobros marcados como vencidos.')
    marcar_como_vencido.short_description = "❌ Marcar como vencido"

@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'categoria', 'monto', 'tipo_gasto', 'fecha', 'estado', 'es_recurrente']
    list_filter = ['tipo_gasto', 'estado', 'categoria', 'es_recurrente']
    search_fields = ['nombre', 'descripcion']
    date_hierarchy = 'fecha'
    
    actions = ['marcar_como_pagado']
    
    def marcar_como_pagado(self, request, queryset):
        queryset.update(estado='pagado', fecha_pago=timezone.now().date())
        self.message_user(request, f'{queryset.count()} gastos marcados como pagados.')
    marcar_como_pagado.short_description = "✅ Marcar como pagado"

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'titulo', 'leida', 'fecha_creacion']
    list_filter = ['tipo', 'leida']
    
    actions = ['marcar_como_leidas']
    
    def marcar_como_leidas(self, request, queryset):
        queryset.update(leida=True)
        self.message_user(request, f'{queryset.count()} notificaciones marcadas como leídas.')
    marcar_como_leidas.short_description = "✅ Marcar como leídas"