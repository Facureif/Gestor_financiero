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
        
        categorias = [
            {'nombre': 'Suscripción SaaS', 'tipo': 'ingreso', 'icono': '💻', 'color': '#27ae60'},
            {'nombre': 'Servicios', 'tipo': 'gasto', 'icono': '⚡', 'color': '#f39c12'},
            {'nombre': 'Impuestos', 'tipo': 'gasto', 'icono': '📋', 'color': '#c0392b'},
            {'nombre': 'Alquiler', 'tipo': 'gasto', 'icono': '🏠', 'color': '#e74c3c'},
            {'nombre': 'Suscripciones', 'tipo': 'gasto', 'icono': '🔔', 'color': '#9b59b6'},
            {'nombre': 'Salud', 'tipo': 'gasto', 'icono': '🏥', 'color': '#e91e63'},
            {'nombre': 'Transporte', 'tipo': 'gasto', 'icono': '🚌', 'color': '#95a5a6'},
        ]
        
        for cat in categorias:
            Categoria.objects.get_or_create(usuario=user, nombre=cat['nombre'], defaults=cat)
        
        clientes_data = [
            {'nombre': 'Transportes Norte SA', 'sistema': 'Gestión Flotas', 'plan': 'Enterprise', 'monto': 250000},
            {'nombre': 'Autos del Sur', 'sistema': 'Concesionaria Pro', 'plan': 'Premium', 'monto': 180000},
            {'nombre': 'Moto Express', 'sistema': 'Gestión Taller', 'plan': 'Básico', 'monto': 95000},
        ]
        
        hoy = date.today()
        
        for c in clientes_data:
            cliente, _ = Cliente.objects.get_or_create(
                usuario=user, nombre=c['nombre'],
                defaults={'sistema': c['sistema'], 'plan': c['plan']}
            )
            
            for i in range(-4, 7):
                fecha = hoy + relativedelta(months=i)
                estado = 'pagado' if fecha < hoy else 'pendiente'
                Cobro.objects.get_or_create(
                    usuario=user, cliente=cliente, fecha_vencimiento=fecha,
                    defaults={
                        'nombre_cliente': cliente.nombre,
                        'monto_total': c['monto'],
                        'monto_pagado': c['monto'] if estado == 'pagado' else 0,
                        'estado': estado, 'es_recurrente': True, 'periodicidad': 'mensual',
                    }
                )
        
        self.stdout.write(self.style.SUCCESS('✅ Datos demo creados: demo / demo123456'))