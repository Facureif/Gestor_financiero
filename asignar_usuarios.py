import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from finances.models import Cobro, Gasto, Cliente, Categoria
from django.contrib.auth.models import User

# Tomar el primer usuario (admin)
admin = User.objects.first()

if admin:
    Cobro.objects.filter(usuario__isnull=True).update(usuario=admin)
    Gasto.objects.filter(usuario__isnull=True).update(usuario=admin)
    Cliente.objects.filter(usuario__isnull=True).update(usuario=admin)
    Categoria.objects.filter(usuario__isnull=True).update(usuario=admin)
    print(f"✅ Datos asignados a: {admin.username}")
else:
    print("❌ No hay usuarios")