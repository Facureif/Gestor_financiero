import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from finances.models import Categoria

# Lista de categorías para crear
categorias = [
    # INGRESOS
    {'nombre': 'Suscripción SaaS', 'tipo': 'ingreso', 'icono': '💻', 'color': '#27ae60'},
    {'nombre': 'Salario', 'tipo': 'ingreso', 'icono': '💰', 'color': '#2ecc71'},
    {'nombre': 'Freelance', 'tipo': 'ingreso', 'icono': '💼', 'color': '#3498db'},
    {'nombre': 'Inversiones', 'tipo': 'ingreso', 'icono': '📈', 'color': '#1abc9c'},
    
    # GASTOS
    {'nombre': 'Alquiler', 'tipo': 'gasto', 'icono': '🏠', 'color': '#e74c3c'},
    {'nombre': 'Suscripciones', 'tipo': 'Suscripción', 'icono': '🔔', 'color': '#f39c12'},
    {'nombre': 'Internet', 'tipo': 'gasto', 'icono': '🌐', 'color': '#3498db'},
    {'nombre': 'Supermercado', 'tipo': 'gasto', 'icono': '🛒', 'color': '#e74c3c'},
    {'nombre': 'Transporte', 'tipo': 'gasto', 'icono': '🚌', 'color': '#95a5a6'},
    {'nombre': 'Obra Social', 'tipo': 'gasto', 'icono': '🏥', 'color': '#e91e63'},
    {'nombre': 'Seguro', 'tipo': 'gasto', 'icono': '🛡️', 'color': '#34495e'},
    {'nombre': 'Teléfono', 'tipo': 'gasto', 'icono': '📱', 'color': '#9b59b6'},
    {'nombre': 'Impuestos', 'tipo': 'gasto', 'icono': '📋', 'color': '#c0392b'},
    {'nombre': 'Software/Herramientas', 'tipo': 'gasto', 'icono': '🔧', 'color': '#7f8c8d'},
]

print("🏷️  Creando categorías...\n")

for cat_data in categorias:
    categoria, creada = Categoria.objects.get_or_create(
        nombre=cat_data['nombre'],
        defaults={
            'tipo': cat_data['tipo'],
            'icono': cat_data['icono'],
            'color': cat_data['color'],
            'activo': True
        }
    )
    
    if creada:
        print(f"✅ Creada: {cat_data['icono']} {cat_data['nombre']} ({cat_data['tipo']})")
    else:
        print(f"⏭️  Ya existe: {cat_data['icono']} {cat_data['nombre']}")

print(f"\n📊 Total de categorías: {Categoria.objects.count()}")
print(f"   - Ingresos: {Categoria.objects.filter(tipo='ingreso').count()}")
print(f"   - Gastos: {Categoria.objects.filter(tipo='gasto').count()}")
print("🎉 ¡Listo! Las categorías ya deberían aparecer en los formularios.")