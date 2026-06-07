import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from finances.models import Categoria

# 1. PRIMERO: Desactivar las categorías viejas que ya no usas
viejas_a_desactivar = ['Obra Social', 'Internet','Seguro', 'Software/Herramientas', 'Teléfono'  ]
for nombre in viejas_a_desactivar:
    Categoria.objects.filter(nombre=nombre).update(activo=False)
    print(f"🔒 Desactivada: {nombre}")

# 2. SEGUNDO: Lista NUEVA de categorías englobadas
categorias = [
    # INGRESOS
    {'nombre': 'Suscripción SaaS', 'tipo': 'ingreso', 'icono': '💻', 'color': '#27ae60'},
    {'nombre': 'Salario', 'tipo': 'ingreso', 'icono': '💰', 'color': '#2ecc71'},
    {'nombre': 'Trabajos Freelance', 'tipo': 'ingreso', 'icono': '💼', 'color': '#3498db'},
    
    # GASTOS AGRUPADOS
    {'nombre': 'Servicios', 'tipo': 'gasto', 'icono': '⚡', 'color': '#f39c12',
     'descripcion': 'Luz, Gas, Internet, Teléfono'},

    {'nombre': 'Impuestos', 'tipo': 'gasto', 'icono': '📋', 'color': '#c0392b',
     'descripcion': 'Monotributo, IVA, Ganancias, Inmobiliario, Patente'},

    {'nombre': 'Alquiler', 'tipo': 'gasto', 'icono': '🏠', 'color': '#e74c3c'},

    {'nombre': 'Suscripciones', 'tipo': 'gasto', 'icono': '🔔', 'color': '#9b59b6',
     'descripcion': 'Netflix, Spotify, Disney, Flow, YouTube'},

    {'nombre': 'Supermercado', 'tipo': 'gasto', 'icono': '🛒', 'color': '#e67e22'},

    {'nombre': 'Transporte', 'tipo': 'gasto', 'icono': '🚌', 'color': '#95a5a6',
     'descripcion': 'Combustible, Saeta, Uber, Estacionamiento'},

    {'nombre': 'Salud', 'tipo': 'gasto', 'icono': '🏥', 'color': '#e91e63',
     'descripcion': 'Obra Social, Prepaga, Medicamentos, Médicos'},

    {'nombre': 'Seguros', 'tipo': 'gasto', 'icono': '🛡️', 'color': '#34495e',
     'descripcion': 'Auto, Vida, Casa, Accidentes'},

    {'nombre': 'Software', 'tipo': 'gasto', 'icono': '🔧', 'color': '#7f8c8d',
     'descripcion': 'Herramientas, Hosting, Dominios, APIs'},
     
    {'nombre': 'Varios', 'tipo': 'gasto', 'icono': '📦', 'color': '#795548',
     'descripcion': 'Gastos que no encajan en otras categorías'},
]

print("\n🏷️  Creando/Actualizando categorías...\n")

for cat_data in categorias:
    categoria, creada = Categoria.objects.update_or_create(
        nombre=cat_data['nombre'],
        defaults={
            'tipo': cat_data['tipo'],
            'icono': cat_data['icono'],
            'color': cat_data['color'],
            'activo': True
        }
    )
    
    if creada:
        print(f"✅ Creada: {cat_data['icono']} {cat_data['nombre']}")
    else:
        print(f"🔄 Actualizada: {cat_data['icono']} {cat_data['nombre']}")

print(f"\n📊 Total categorías activas: {Categoria.objects.filter(activo=True).count()}")
print(f"   - Ingresos: {Categoria.objects.filter(tipo='ingreso', activo=True).count()}")
print(f"   - Gastos: {Categoria.objects.filter(tipo='gasto', activo=True).count()}")
print(f"\n🔒 Categorías inactivas: {Categoria.objects.filter(activo=False).count()}")
print("🎉 ¡Listo!")