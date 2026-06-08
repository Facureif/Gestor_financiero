from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from finances.models import Categoria, Cliente, Cobro, Gasto
from datetime import date
from dateutil.relativedelta import relativedelta

class Command(BaseCommand):
    help = 'Crea datos demo para la aplicación'

    def handle(self, *args, **kwargs):
        if User.objects.filter(username='demo').exists():
            self.stdout.write('⏭️ Datos demo ya existen')
            return

        self.stdout.write('🎮 Creando datos demo...')
        
        user = User.objects.create_user('demo', password='demo123456')
        
        # ========== CATEGORÍAS ==========
        categorias = [
            {'nombre': 'Suscripción SaaS', 'tipo': 'ingreso', 'icono': '💻', 'color': '#27ae60'},
            {'nombre': 'Servicios', 'tipo': 'gasto', 'icono': '⚡', 'color': '#f39c12'},
            {'nombre': 'Impuestos', 'tipo': 'gasto', 'icono': '📋', 'color': '#c0392b'},
            {'nombre': 'Alquiler', 'tipo': 'gasto', 'icono': '🏠', 'color': '#e74c3c'},
            {'nombre': 'Suscripciones', 'tipo': 'gasto', 'icono': '🔔', 'color': '#9b59b6'},
            {'nombre': 'Salud', 'tipo': 'gasto', 'icono': '🏥', 'color': '#e91e63'},
            {'nombre': 'Transporte', 'tipo': 'gasto', 'icono': '🚌', 'color': '#95a5a6'},
            {'nombre': 'Software', 'tipo': 'gasto', 'icono': '🔧', 'color': '#7f8c8d'},
            {'nombre': 'Varios', 'tipo': 'gasto', 'icono': '📦', 'color': '#795548'},
        ]
        
        for cat in categorias:
            Categoria.objects.get_or_create(usuario=user, nombre=cat['nombre'], defaults=cat)
        
        cat_saas = Categoria.objects.get(usuario=user, nombre='Suscripción SaaS')
        cat_servicios = Categoria.objects.get(usuario=user, nombre='Servicios')
        cat_impuestos = Categoria.objects.get(usuario=user, nombre='Impuestos')
        cat_alquiler = Categoria.objects.get(usuario=user, nombre='Alquiler')
        cat_susc = Categoria.objects.get(usuario=user, nombre='Suscripciones')
        cat_salud = Categoria.objects.get(usuario=user, nombre='Salud')
        cat_transporte = Categoria.objects.get(usuario=user, nombre='Transporte')
        cat_software = Categoria.objects.get(usuario=user, nombre='Software')
        
        # ========== CLIENTES ==========
        clientes_data = [
            {'nombre': 'Transportes Norte SA', 'sistema': 'Gestión Flotas', 'plan': 'Enterprise', 'monto': 250000},
            {'nombre': 'Autos del Sur', 'sistema': 'Concesionaria Pro', 'plan': 'Premium', 'monto': 180000},
            {'nombre': 'Moto Express', 'sistema': 'Gestión Taller', 'plan': 'Básico', 'monto': 95000},
        ]
        
        hoy = date.today()
        
        for c in clientes_data:
            cliente, _ = Cliente.objects.get_or_create(
                usuario=user, nombre=c['nombre'],
                defaults={
                    'sistema': c['sistema'], 
                    'plan': c['plan'],
                    'email': f"info@{c['nombre'].lower().replace(' ', '')}.com",
                    'telefono': '11-5555-0000',
                }
            )
            
            # Cobros: 4 meses atrás + 6 meses adelante
            for i in range(-4, 7):
                fecha = hoy + relativedelta(months=i)
                estado = 'pagado' if fecha < hoy else 'pendiente'
                Cobro.objects.get_or_create(
                    usuario=user, cliente=cliente, fecha_vencimiento=fecha,
                    defaults={
                        'nombre_cliente': cliente.nombre,
                        'sistema': cliente.sistema,
                        'plan': cliente.plan,
                        'monto_total': c['monto'],
                        'monto_pagado': c['monto'] if estado == 'pagado' else 0,
                        'estado': estado,
                        'es_recurrente': True,
                        'periodicidad': 'mensual',
                        'forma_pago': 'transferencia',
                    }
                )
        
        # ========== GASTOS FIJOS ==========
        gastos_data = [
            # (categoría, nombre, monto, tipo, pago_auto, periodicidad)
            (cat_alquiler, 'Oficina Coworking', 120000, 'fijo', False, 'mensual'),
            (cat_servicios, 'Electricidad Edesur', 25000, 'servicio', False, 'mensual'),
            (cat_servicios, 'Agua AYSA', 8000, 'servicio', False, 'mensual'),
            (cat_susc, 'Internet + TV', 15000, 'fijo', True, 'mensual'),
            (cat_susc, 'Netflix Premium', 4500, 'fijo', True, 'mensual'),
            (cat_susc, 'Spotify', 1200, 'fijo', True, 'mensual'),
            (cat_susc, 'Google Workspace', 8500, 'fijo', True, 'mensual'),
            (cat_salud, 'Obra Social OSDE', 45000, 'fijo', True, 'mensual'),
            (cat_impuestos, 'Monotributo', 35000, 'impuesto', False, 'mensual'),
            (cat_impuestos, 'Ingresos Brutos', 12000, 'impuesto', False, 'mensual'),
            (cat_software, 'Hosting VPS', 15000, 'fijo', True, 'mensual'),
            (cat_software, 'Dominios (.com.ar)', 3000, 'fijo', True, 'anual'),
            (cat_transporte, 'Combustible', 30000, 'variable', False, 'unico'),
        ]
        
        for cat, nombre, monto, tipo, pago_auto, periodicidad in gastos_data:
            for i in range(-2, 3):
                fecha = hoy + relativedelta(months=i)
                estado = 'pagado' if fecha < hoy else 'pendiente'
                
                Gasto.objects.get_or_create(
                    usuario=user,
                    categoria=cat,
                    nombre=nombre,
                    fecha_vencimiento=fecha,
                    defaults={
                        'monto': monto,
                        'estado': estado,
                        'fecha': fecha,
                        'es_recurrente': True,
                        'pago_automatico': pago_auto,
                        'periodicidad': periodicidad,
                        'tipo_gasto': tipo,
                        'forma_pago': 'debito_automatico' if pago_auto else 'transferencia',
                    }
                )
        
        self.stdout.write(self.style.SUCCESS(f'''
✅ Datos demo creados exitosamente!
   👤 Usuario: demo / demo123456
   💵 Cobros: {Cobro.objects.filter(usuario=user).count()}
   🛒 Gastos: {Gasto.objects.filter(usuario=user).count()}
   👥 Clientes: {Cliente.objects.filter(usuario=user).count()}
        '''))