from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def login_view(request):
    """Vista de inicio de sesión"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'✅ Bienvenido, {username}!')
                return redirect('dashboard')
        else:
            messages.error(request, '❌ Usuario o contraseña incorrectos')
    else:
        form = AuthenticationForm()
    
    return render(request, 'usuarios/login.html', {'form': form})

def registro_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Crear categorías por defecto para el nuevo usuario
            crear_categorias_default(user)
            
            login(request, user)
            messages.success(request, '✅ Cuenta creada exitosamente!')
            return redirect('dashboard')
        else:
            messages.error(request, '❌ Error en el registro.')
    else:
        form = UserCreationForm()
    
    return render(request, 'usuarios/registro.html', {'form': form})

def crear_categorias_default(user):
    """Crea categorías iniciales para un usuario nuevo"""
    categorias = [
        {'nombre': 'Suscripción SaaS', 'tipo': 'ingreso', 'icono': '💻', 'color': '#27ae60'},
        {'nombre': 'Salario', 'tipo': 'ingreso', 'icono': '💰', 'color': '#2ecc71'},
        {'nombre': 'Servicios', 'tipo': 'gasto', 'icono': '⚡', 'color': '#f39c12'},
        {'nombre': 'Impuestos', 'tipo': 'gasto', 'icono': '📋', 'color': '#c0392b'},
        {'nombre': 'Alquiler', 'tipo': 'gasto', 'icono': '🏠', 'color': '#e74c3c'},
        {'nombre': 'Suscripciones', 'tipo': 'gasto', 'icono': '🔔', 'color': '#9b59b6'},
        {'nombre': 'Supermercado', 'tipo': 'gasto', 'icono': '🛒', 'color': '#e67e22'},
        {'nombre': 'Salud', 'tipo': 'gasto', 'icono': '🏥', 'color': '#e91e63'},
        {'nombre': 'Transporte', 'tipo': 'gasto', 'icono': '🚌', 'color': '#95a5a6'},
        {'nombre': 'Varios', 'tipo': 'gasto', 'icono': '📦', 'color': '#795548'},
    ]
    
    from finances.models import Categoria
    for cat in categorias:
        Categoria.objects.get_or_create(
            usuario=user,
            nombre=cat['nombre'],
            defaults={
                'tipo': cat['tipo'],
                'icono': cat['icono'],
                'color': cat['color'],
                'activo': True
            }
        )

def logout_view(request):
    """Cerrar sesión"""
    logout(request)
    messages.success(request, '👋 Sesión cerrada')
    return redirect('login')