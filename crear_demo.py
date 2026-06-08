import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from finances.models import Categoria, Cliente, Cobro, Gasto
from django.contrib.auth.models import User

# Crear usuario demo
user, created = User.objects.get_or_create(
    username='demo',
    defaults={'is_active': True}
)
if created:
    user.set_password('demo123456')
    user.save()
    print("✅ Usuario demo creado (demo / demo123456)")

# Crear categorías
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

# Crear clientes demo
clientes_data = [
    {'nombre': 'Transportes Norte SA', 'sistema': 'Gestión Flotas', 'plan': 'Enterprise', 'monto': 250000},
    {'nombre': 'Autos del Sur', 'sistema': 'Concesionaria Pro', 'plan': 'Premium', 'monto': 180000},
    {'nombre': 'Moto Express', 'sistema': 'Gestión Taller', 'plan': 'Básico', 'monto': 95000},
]

clientes = []
for c in clientes_data:
    cliente, _ = Cliente.objects.get_or_create(
        usuario=user,
        nombre=c['nombre'],
        defaults={
            'sistema': c['sistema'],
            'plan': c['plan'],
            'email': f"info@{c['nombre'].lower().replace(' ', '')}.com",
            'telefono': '11-5555-0000',
        }
    )
    clientes.append((cliente, c['monto']))

# Crear cobros de los últimos 3 meses
hoy = date.today()
categoria_saas = Categoria.objects.get(usuario=user, nombre='Suscripción SaaS')

for cliente, monto in clientes:
    # Crear cobros de los últimos 4 meses y próximos 6 meses
    from dateutil.relativedelta import relativedelta
    for i in range(-4, 7):
        fecha = hoy + relativedelta(months=i)
        estado = 'pagado' if fecha < hoy else 'pendiente'
        monto_pagado = monto if estado == 'pagado' else 0
        
        Cobro.objects.get_or_create(
            usuario=user,
            cliente=cliente,
            fecha_vencimiento=fecha,
            defaults={
                'nombre_cliente': cliente.nombre,
                'sistema': cliente.sistema,
                'plan': cliente.plan,
                'monto_total': monto,
                'monto_pagado': monto_pagado,
                'estado': estado,
                'es_recurrente': True,
                'periodicidad': 'mensual',
            }
        )

# Crear gastos demo
gastos_data = [
    ('Alquiler', 'Alquiler', 120000, 'mensual'),
    ('Servicios', 'Electricidad', 25000, 'mensual'),
    ('Suscripciones', 'Internet + TV', 15000, 'mensual'),
    ('Salud', 'Obra Social', 45000, 'mensual'),
    ('Impuestos', 'Monotributo', 35000, 'mensual'),
    ('Transporte', 'Combustible', 30000, 'variable'),
]

for cat_nombre, nombre, monto, tipo in gastos_data:
    cat = Categoria.objects.get(usuario=user, nombre=cat_nombre)
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
                'periodicidad': 'mensual' if tipo == 'mensual' else 'unico',
                'tipo_gasto': 'fijo' if tipo == 'mensual' else 'variable',
            }
        )

print(f"✅ Datos demo creados!")
print(f"   Cobros: {Cobro.objects.filter(usuario=user).count()}")
print(f"   Gastos: {Gasto.objects.filter(usuario=user).count()}")
print(f"   Clientes: {Cliente.objects.filter(usuario=user).count()}")
print(f"\n🔑 Login demo: usuario=demo, contraseña=demo123456")