from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Q
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Categoria, Cliente, Cobro, Gasto, Notificacion
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar
import json
import openpyxl
from io import BytesIO
from decimal import Decimal


# ============ FUNCIONES HELPER ============

def hoy_local():
    """Devuelve la fecha actual en la zona horaria local"""
    return timezone.localtime(timezone.now()).date()

def actualizar_cobros_vencidos():
    """Cambia a 'vencido' los cobros y crea notificaciones"""
    hoy = hoy_local()
    
    # Buscar cobros que acaban de vencer (los que estaban pendientes/parciales y ya pasó su fecha)
    cobros_vencidos = Cobro.objects.filter(
        estado__in=['pendiente', 'parcial'],
        fecha_vencimiento__lt=hoy
    )
    
    # Crear notificación por cada uno
    for cobro in cobros_vencidos:
        Notificacion.objects.get_or_create(
            cobro=cobro,
            tipo='cobro_vencido',
            defaults={
                'titulo': f'⚠️ Cobro vencido: {cobro.nombre_cliente}',
                'mensaje': f'El cobro de {cobro.nombre_cliente} por ${cobro.saldo:,.2f} venció el {cobro.fecha_vencimiento.strftime("%d/%m/%Y")}.'
            }
        )
    
    # Marcar como vencidos
    actualizados = cobros_vencidos.update(estado='vencido')
    return actualizados

def actualizar_gastos_vencidos():
    """Cambia a 'vencido' los gastos que ya pasaron su fecha"""
    hoy = hoy_local()
    return Gasto.objects.filter(
        estado='pendiente',
        fecha_vencimiento__lt=hoy
    ).update(estado='vencido')


# ============ DASHBOARD ============

@login_required
def dashboard(request):
    actualizar_cobros_vencidos()
    crear_notificaciones_proximas()
    actualizar_gastos_vencidos()
    hoy = hoy_local()
    mes_actual = hoy.month
    año_actual = hoy.year
    
    # ----- COBROS -----
    cobros_mes = Cobro.objects.filter(
        usuario=request.user,
        fecha_vencimiento__year=año_actual,
        fecha_vencimiento__month=mes_actual
    )
    total_a_cobrar = cobros_mes.aggregate(total=Sum('monto_total'))['total'] or 0
    total_cobrado = cobros_mes.aggregate(total=Sum('monto_pagado'))['total'] or 0
    pendiente_cobrar = total_a_cobrar - total_cobrado
    
    # Efectividad de cobranza
    if total_a_cobrar > 0:
        porcentaje_cobranza = (total_cobrado / total_a_cobrar) * 100
        porcentaje_pendiente = 100 - porcentaje_cobranza
    else:
        porcentaje_cobranza = 0
        porcentaje_pendiente = 0
    
    # Próximos cobros (7 días)
    proximos_cobros = Cobro.objects.filter(
        usuario=request.user,
        estado__in=['pendiente', 'parcial'],
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=hoy + timedelta(days=7)
    ).order_by('fecha_vencimiento')
    
    # Cobros vencidos
    cobros_vencidos = Cobro.objects.filter(
        usuario=request.user,
        estado='vencido'
    ).order_by('fecha_vencimiento')[:10]
    
    # Últimos cobros
    ultimos_cobros = Cobro.objects.filter(
        usuario=request.user
    ).order_by('-actualizado')[:5]
    
    # ----- GASTOS -----
    gastos_mes = Gasto.objects.filter(
        usuario=request.user,
        fecha__year=año_actual,
        fecha__month=mes_actual
    )
    total_gastos = gastos_mes.aggregate(total=Sum('monto'))['total'] or 0
    
    # Gastos por categoría (gráfico)
    gastos_categoria = Gasto.objects.filter(
        usuario=request.user,
        fecha__year=año_actual,
        fecha__month=mes_actual,
        monto__isnull=False
    ).values('categoria__nombre', 'categoria__color').annotate(
        total=Sum('monto')
    ).order_by('-total')
    
    categorias_gastos_json = json.dumps([
        {'nombre': c['categoria__nombre'], 'color': c['categoria__color'], 'total': float(c['total'])}
        for c in gastos_categoria
    ])
    
    # Próximos gastos
    proximos_gastos = Gasto.objects.filter(
        usuario=request.user,
        estado='pendiente',
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=hoy + timedelta(days=7)
    ).order_by('fecha_vencimiento')
    
    # Balance
    balance = total_cobrado - total_gastos
    
    # Notificaciones
    total_no_leidas = Notificacion.objects.filter(
    cobro__usuario=request.user,  # AGREGAR
    leida=False
).count()
    
    context = {
        'total_a_cobrar': total_a_cobrar,
        'total_cobrado': total_cobrado,
        'pendiente_cobrar': pendiente_cobrar,
        'porcentaje_cobranza': porcentaje_cobranza,
        'porcentaje_pendiente': porcentaje_pendiente,
        'total_gastos': total_gastos,
        'balance': balance,
        'proximos_cobros': proximos_cobros,
        'cobros_vencidos': cobros_vencidos,
        'ultimos_cobros': ultimos_cobros,
        'proximos_gastos': proximos_gastos,
        'categorias_gastos_json': categorias_gastos_json,
        'total_no_leidas': total_no_leidas,
        'mes_actual': calendar.month_name[mes_actual],
        'año_actual': año_actual,
    }
    return render(request, 'finances/dashboard.html', context)


# ============ COBROS ============

@login_required
def lista_cobros(request):
    actualizar_cobros_vencidos()
    hoy = hoy_local()
    
    mes = request.GET.get('mes', hoy.month)
    año = request.GET.get('año', hoy.year)
    estado = request.GET.get('estado', '')
    buscar = request.GET.get('buscar', '')
    
    cobros = Cobro.objects.filter(usuario=request.user)
    
    if mes:
        mes = int(mes)
        if año:
            año = int(año)
            cobros = cobros.filter(fecha_vencimiento__month=mes, fecha_vencimiento__year=año)
    elif año:
        año = int(año)
        cobros = cobros.filter(fecha_vencimiento__year=año)
    
    if estado:
        cobros = cobros.filter(estado=estado)
    
    if buscar:
        cobros = cobros.filter(
            Q(nombre_cliente__icontains=buscar) |
            Q(sistema__icontains=buscar) |
            Q(plan__icontains=buscar)
        )
    
    cobros = cobros.order_by('fecha_vencimiento')
    
    totales = cobros.aggregate(
        total=Sum('monto_total'),
        pagado=Sum('monto_pagado'),
        pendiente=Sum('saldo')
    )
    
    context = {
        'cobros': cobros,
        'totales': totales,
        'meses': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'años': range(2024, hoy.year + 2),
        'filtros': {
            'mes': int(mes) if mes else '',
            'año': int(año) if año else '',
            'estado': estado,
            'buscar': buscar,
        },
    }
    return render(request, 'finances/lista_cobros.html', context)


@login_required
def crear_cobro(request):
    if request.method == 'POST':
        try:
            monto_total = float(request.POST.get('monto_total', 0) or 0)
            monto_pagado = float(request.POST.get('monto_pagado', 0) or 0)
            meses_a_generar = int(request.POST.get('meses_a_generar', 1) or 1)
            es_recurrente = request.POST.get('es_recurrente') == 'on'
            cliente_id = request.POST.get('cliente') or None
            
            fecha_str = request.POST.get('fecha_vencimiento')
            fecha_vencimiento = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            fecha_emision = hoy_local()
            
            cobro_base = Cobro.objects.create(
                usuario=request.user,
                cliente_id=cliente_id,
                nombre_cliente=request.POST.get('nombre_cliente'),
                sistema=request.POST.get('sistema', ''),
                plan=request.POST.get('plan', ''),
                monto_total=monto_total,
                monto_pagado=monto_pagado,
                fecha_emision=fecha_emision,
                fecha_vencimiento=fecha_vencimiento,
                es_recurrente=es_recurrente,
                periodicidad=request.POST.get('periodicidad', 'mensual'),
                forma_pago=request.POST.get('forma_pago', 'transferencia'),
                observaciones=request.POST.get('observaciones', ''),
                meses_a_generar=meses_a_generar,
            )
            
            if request.FILES.get('comprobante'):
                cobro_base.comprobante = request.FILES['comprobante']
                cobro_base.save()
            
            cobros_creados = 1
            if es_recurrente and meses_a_generar > 1:
                fecha_actual = fecha_vencimiento
                
                for i in range(1, meses_a_generar):
                    if cobro_base.periodicidad == 'mensual':
                        fecha_actual = fecha_actual + relativedelta(months=1)
                    elif cobro_base.periodicidad == 'quincenal':
                        fecha_actual = fecha_actual + relativedelta(days=15)
                    elif cobro_base.periodicidad == 'bimestral':
                        fecha_actual = fecha_actual + relativedelta(months=2)
                    elif cobro_base.periodicidad == 'trimestral':
                        fecha_actual = fecha_actual + relativedelta(months=3)
                    elif cobro_base.periodicidad == 'semestral':
                        fecha_actual = fecha_actual + relativedelta(months=6)
                    elif cobro_base.periodicidad == 'anual':
                        fecha_actual = fecha_actual + relativedelta(years=1)
                    else:
                        fecha_actual = fecha_actual + relativedelta(months=1)
                    
                    Cobro.objects.create(
                        usuario=request.user,
                        cliente_id=cliente_id,
                        nombre_cliente=cobro_base.nombre_cliente,
                        sistema=cobro_base.sistema,
                        plan=cobro_base.plan,
                        monto_total=monto_total,
                        monto_pagado=0,
                        fecha_emision=hoy_local(),
                        fecha_vencimiento=fecha_actual,
                        estado='pendiente',
                        forma_pago=cobro_base.forma_pago,
                        es_recurrente=True,
                        periodicidad=cobro_base.periodicidad,
                        meses_a_generar=1,
                        observaciones=f'Generado auto - Mes {i+1}/{meses_a_generar}'
                    )
                    cobros_creados += 1
            
            messages.success(request, f'✅ {cobros_creados} cobro(s) creado(s)')
            return redirect('lista_cobros')
            
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    clientes = Cliente.objects.filter(usuario=request.user, activo=True)
    return render(request, 'finances/form_cobro.html', {'clientes': clientes})


@login_required
def editar_cobro(request, pk):
    cobro = get_object_or_404(Cobro, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        try:
            cobro.cliente_id = request.POST.get('cliente') or None
            cobro.nombre_cliente = request.POST.get('nombre_cliente')
            cobro.sistema = request.POST.get('sistema', '')
            cobro.plan = request.POST.get('plan', '')
            cobro.monto_total = request.POST.get('monto_total')
            cobro.monto_pagado = request.POST.get('monto_pagado', 0)
            cobro.fecha_vencimiento = request.POST.get('fecha_vencimiento')
            cobro.estado = request.POST.get('estado', 'pendiente')
            cobro.forma_pago = request.POST.get('forma_pago', 'transferencia')
            cobro.observaciones = request.POST.get('observaciones', '')
            
            actualizar_siguientes = request.POST.get('actualizar_siguientes') == 'on'
            
            if request.FILES.get('comprobante'):
                cobro.comprobante = request.FILES['comprobante']
            
            cobro.save()
            
            if actualizar_siguientes:
                nuevo_monto = Decimal(str(cobro.monto_total))
                
                siguientes = Cobro.objects.filter(
                    usuario=request.user,
                    nombre_cliente=cobro.nombre_cliente,
                    fecha_vencimiento__gt=cobro.fecha_vencimiento,
                    estado__in=['pendiente', 'parcial']
                )
                
                actualizados = 0
                for c in siguientes:
                    c.monto_total = nuevo_monto
                    c.monto_pagado = Decimal('0')
                    c.save()
                    actualizados += 1
                
                messages.success(request, f'✅ Cobro actualizado y {actualizados} siguientes ajustados')
            else:
                messages.success(request, '✅ Cobro actualizado')
            
            return redirect('lista_cobros')
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    clientes = Cliente.objects.filter(usuario=request.user, activo=True)
    return render(request, 'finances/form_cobro.html', {'cobro': cobro, 'clientes': clientes})


@login_required
def eliminar_cobro(request, pk):
    cobro = get_object_or_404(Cobro, pk=pk, usuario=request.user)
    if request.method == 'POST':
        nombre = cobro.nombre_cliente
        cobro.delete()
        messages.success(request, f'🗑️ Cobro de {nombre} eliminado')
        return redirect('lista_cobros')
    return render(request, 'finances/confirmar_eliminar.html', {'cobro': cobro})


@login_required
def generar_cobro_siguiente(request, pk):
    cobro_original = get_object_or_404(Cobro, pk=pk, usuario=request.user)
    nueva_fecha = cobro_original.fecha_vencimiento + relativedelta(months=1)
    
    nuevo_cobro = Cobro.objects.create(
        usuario=request.user,
        cliente=cobro_original.cliente,
        nombre_cliente=cobro_original.nombre_cliente,
        sistema=cobro_original.sistema,
        plan=cobro_original.plan,
        monto_total=cobro_original.monto_total,
        monto_pagado=0,
        fecha_emision=hoy_local(),
        fecha_vencimiento=nueva_fecha,
        es_recurrente=cobro_original.es_recurrente,
        periodicidad=cobro_original.periodicidad,
        forma_pago=cobro_original.forma_pago,
        observaciones=f'Generado desde cobro {cobro_original.id}'
    )
    
    messages.success(request, f'✅ Cobro generado - Vence: {nueva_fecha.strftime("%d/%m/%Y")}')
    return redirect('lista_cobros')


@login_required
def registrar_pago(request, pk):
    cobro = get_object_or_404(Cobro, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        monto = request.POST.get('monto_pagado', '0')
        monto = float(monto) if monto else 0
        
        if monto > 0:
            cobro.monto_pagado = Decimal(str(cobro.monto_pagado)) + Decimal(str(monto))
            cobro.fecha_pago = hoy_local()
            
            if request.FILES.get('comprobante'):
                cobro.comprobante = request.FILES['comprobante']
            
            cobro.save()
            messages.success(request, f'✅ Pago de ${monto:,.2f} registrado')
        return redirect('lista_cobros')
    
    return render(request, 'finances/registrar_pago.html', {'cobro': cobro})


@login_required
def historial_cliente(request, nombre):
    actualizar_cobros_vencidos()
    cobros = Cobro.objects.filter(
        usuario=request.user,
        nombre_cliente__icontains=nombre
    ).order_by('-fecha_vencimiento')
    
    historial = {}
    for c in cobros:
        año = c.fecha_vencimiento.year
        if año not in historial:
            historial[año] = []
        historial[año].append(c)
    
    cliente = None
    if cobros.exists():
        cliente = cobros.first().cliente
        if not cliente:
            cliente = Cliente.objects.filter(
                usuario=request.user
            ).filter(
                Q(nombre__icontains=nombre) | Q(nombre_contacto__icontains=nombre)
            ).first()
    
    context = {
        'nombre': nombre,
        'historial': dict(sorted(historial.items(), reverse=True)),
        'total_cobros': cobros.count(),
        'total_cobrado': cobros.aggregate(total=Sum('monto_pagado'))['total'] or 0,
        'total_pendiente': cobros.aggregate(total=Sum('saldo'))['total'] or 0,
        'cliente': cliente,
    }
    return render(request, 'finances/historial_cliente.html', context)


# ============ RESUMENES DE COBROS ============

@login_required
def resumen_cobros_mensual(request, año=None, mes=None):
    actualizar_cobros_vencidos()
    if not año:
        año = request.GET.get('año', datetime.now().year)
    if not mes:
        mes = request.GET.get('mes', datetime.now().month)
    
    año = int(año)
    mes = int(mes)
    
    cobros = Cobro.objects.filter(
        usuario=request.user,
        fecha_vencimiento__year=año,
        fecha_vencimiento__month=mes
    ).order_by('fecha_vencimiento')
    
    totales = cobros.aggregate(
        total=Sum('monto_total'),
        pagado=Sum('monto_pagado'),
        pendiente=Sum('saldo')
    )
    
    total = totales['total'] or 0
    pagado = totales['pagado'] or 0
    porcentaje = (pagado / total * 100) if total > 0 else 0
    
    context = {
        'cobros': cobros,
        'totales': totales,
        'porcentaje': porcentaje,
        'año': año,
        'mes': mes,
        'nombre_mes': calendar.month_name[mes],
        'meses': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'años': range(2024, datetime.now().year + 2),
    }
    return render(request, 'finances/resumen_mensual.html', context)


@login_required
def resumen_cobros_anual(request, año=None):
    actualizar_cobros_vencidos()
    if not año:
        año = datetime.now().year
    año = int(año)
    
    resumen_mensual = []
    for mes in range(1, 13):
        datos = Cobro.objects.filter(
            usuario=request.user,
            fecha_vencimiento__year=año,
            fecha_vencimiento__month=mes
        ).aggregate(
            total=Sum('monto_total'),
            pagado=Sum('monto_pagado'),
            pendiente=Sum('saldo')
        )
        total = datos['total'] or 0
        pagado = datos['pagado'] or 0
        resumen_mensual.append({
            'mes': mes,
            'nombre': calendar.month_name[mes],
            'total': total,
            'pagado': pagado,
            'pendiente': datos['pendiente'] or 0,
            'porcentaje': (pagado / total * 100) if total > 0 else 0
        })
    
    totales = Cobro.objects.filter(
        usuario=request.user,
        fecha_vencimiento__year=año
    ).aggregate(
        total=Sum('monto_total'),
        pagado=Sum('monto_pagado'),
        pendiente=Sum('saldo')
    )
    
    context = {
        'resumen_mensual': resumen_mensual,
        'totales': totales,
        'año': año,
        'años': range(2024, datetime.now().year + 2),
    }
    return render(request, 'finances/resumen_anual.html', context)


@login_required
def ajustar_precio_desde(request, pk):
    cobro_inicial = get_object_or_404(Cobro, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        nuevo_monto = Decimal(str(request.POST.get('nuevo_monto', 0) or 0))
        
        cobro_inicial.monto_total = nuevo_monto
        cobro_inicial.save()
        
        siguientes = Cobro.objects.filter(
            usuario=request.user,
            nombre_cliente=cobro_inicial.nombre_cliente,
            fecha_vencimiento__gt=cobro_inicial.fecha_vencimiento,
            estado__in=['pendiente', 'parcial']
        )
        
        actualizados = 1
        for c in siguientes:
            c.monto_total = nuevo_monto
            c.save()
            actualizados += 1
        
        messages.success(request, f'✅ {actualizados} cobros actualizados')
        return redirect('lista_cobros')
    
    return render(request, 'finances/ajustar_precio.html', {'cobro': cobro_inicial})


# ============ GASTOS ============

@login_required
def lista_gastos(request):
    actualizar_gastos_vencidos()
    hoy = hoy_local()
    
    mes = request.GET.get('mes', hoy.month)
    año = request.GET.get('año', hoy.year)
    estado = request.GET.get('estado', '')
    buscar = request.GET.get('buscar', '')
    
    gastos = Gasto.objects.filter(usuario=request.user)
    
    if mes:
        mes = int(mes)
        if año:
            año = int(año)
            gastos = gastos.filter(
                Q(fecha_vencimiento__month=mes, fecha_vencimiento__year=año) |
                Q(fecha_vencimiento__isnull=True, fecha__month=mes, fecha__year=año)
            )
    elif año:
        año = int(año)
        gastos = gastos.filter(
            Q(fecha_vencimiento__year=año) |
            Q(fecha_vencimiento__isnull=True, fecha__year=año)
        )
    
    if estado:
        gastos = gastos.filter(estado=estado)
    
    if buscar:
        gastos = gastos.filter(
            Q(nombre__icontains=buscar) |
            Q(categoria__nombre__icontains=buscar)
        )
    
    gastos = gastos.order_by('estado', 'fecha_vencimiento', 'fecha')
    
    context = {
        'gastos': gastos,
        'nombre_mes': calendar.month_name[int(mes)] if mes else '',
        'meses': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'años': range(2024, hoy.year + 2),
        'filtros': {
            'mes': int(mes) if mes else '',
            'año': int(año) if año else '',
            'estado': estado,
            'buscar': buscar,
        },
    }
    return render(request, 'finances/lista_gastos.html', context)


@login_required
def crear_gasto(request):
    if request.method == 'POST':
        try:
            monto = request.POST.get('monto') or None
            monto = float(monto) if monto else None
            meses_a_generar = int(request.POST.get('meses_a_generar', 1) or 1)
            es_recurrente = request.POST.get('es_recurrente') == 'on'
            pago_automatico = request.POST.get('pago_automatico') == 'on'
            periodicidad = request.POST.get('periodicidad', 'mensual')
            
            fecha_str = request.POST.get('fecha')
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else hoy_local()
            
            vencimiento_str = request.POST.get('fecha_vencimiento')
            fecha_vencimiento = datetime.strptime(vencimiento_str, '%Y-%m-%d').date() if vencimiento_str else None
            
            gasto_base = Gasto.objects.create(
                usuario=request.user,
                categoria_id=request.POST.get('categoria'),
                nombre=request.POST.get('nombre'),
                monto=monto,
                fecha=fecha,
                fecha_vencimiento=fecha_vencimiento,
                forma_pago=request.POST.get('forma_pago', 'efectivo'),
                estado='pendiente',
                es_recurrente=es_recurrente,
                pago_automatico=pago_automatico,
                periodicidad=periodicidad,
                tipo_gasto=request.POST.get('tipo_gasto', 'fijo'),
                observaciones=request.POST.get('observaciones', ''),
                meses_a_generar=meses_a_generar,
            )
            
            if request.FILES.get('comprobante'):
                gasto_base.comprobante = request.FILES['comprobante']
                gasto_base.save()
            
            gastos_creados = 1
            if es_recurrente and meses_a_generar > 1 and fecha_vencimiento:
                fecha_actual = fecha_vencimiento
                
                for i in range(1, meses_a_generar):
                    if periodicidad == 'mensual':
                        fecha_actual = fecha_actual + relativedelta(months=1)
                    elif periodicidad == 'bimestral':
                        fecha_actual = fecha_actual + relativedelta(months=2)
                    elif periodicidad == 'trimestral':
                        fecha_actual = fecha_actual + relativedelta(months=3)
                    elif periodicidad == 'semestral':
                        fecha_actual = fecha_actual + relativedelta(months=6)
                    elif periodicidad == 'anual':
                        fecha_actual = fecha_actual + relativedelta(years=1)
                    else:
                        fecha_actual = fecha_actual + relativedelta(months=1)
                    
                    Gasto.objects.create(
                        usuario=request.user,
                        categoria=gasto_base.categoria,
                        nombre=gasto_base.nombre,
                        monto=monto,
                        fecha=fecha_actual,
                        fecha_vencimiento=fecha_actual,
                        forma_pago=gasto_base.forma_pago,
                        estado='pendiente',
                        es_recurrente=True,
                        pago_automatico=pago_automatico,
                        periodicidad=periodicidad,
                        tipo_gasto=gasto_base.tipo_gasto,
                        meses_a_generar=1,
                        observaciones=f'Generado auto - Mes {i+1}/{meses_a_generar}'
                    )
                    gastos_creados += 1
            
            messages.success(request, f'✅ {gastos_creados} gasto(s) creado(s)')
            return redirect('lista_gastos')
            
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
    
    categorias = Categoria.objects.filter(usuario=request.user, activo=True, tipo='gasto')
    return render(request, 'finances/form_gasto.html', {'categorias': categorias})


@login_required
def pagar_gasto(request, pk):
    gasto = get_object_or_404(Gasto, pk=pk, usuario=request.user)
    gasto.estado = 'pagado'
    gasto.fecha_pago = hoy_local()
    gasto.save()
    messages.success(request, f'✅ Gasto pagado: {gasto.nombre}')
    return redirect('dashboard')


@login_required
def editar_gasto(request, pk):
    gasto = get_object_or_404(Gasto, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        gasto.categoria_id = request.POST.get('categoria')
        gasto.nombre = request.POST.get('nombre')
        gasto.monto = request.POST.get('monto') or None
        gasto.fecha = request.POST.get('fecha') or hoy_local()
        gasto.fecha_vencimiento = request.POST.get('fecha_vencimiento') or None
        gasto.forma_pago = request.POST.get('forma_pago', 'efectivo')
        gasto.estado = request.POST.get('estado', 'pendiente')
        gasto.es_recurrente = request.POST.get('es_recurrente') == 'on'
        gasto.pago_automatico = request.POST.get('pago_automatico') == 'on'
        gasto.periodicidad = request.POST.get('periodicidad', 'unico')
        gasto.observaciones = request.POST.get('observaciones', '')
        
        if request.FILES.get('comprobante'):
            gasto.comprobante = request.FILES['comprobante']
        
        gasto.save()
        messages.success(request, '✅ Gasto actualizado')
        return redirect('lista_gastos')
    
    categorias = Categoria.objects.filter(usuario=request.user, activo=True, tipo='gasto')
    return render(request, 'finances/form_gasto.html', {'gasto': gasto, 'categorias': categorias})


@login_required
def eliminar_gasto(request, pk):
    gasto = get_object_or_404(Gasto, pk=pk, usuario=request.user)
    if request.method == 'POST':
        nombre = gasto.nombre
        gasto.delete()
        messages.success(request, f'🗑️ Gasto "{nombre}" eliminado')
        return redirect('lista_gastos')
    return render(request, 'finances/confirmar_eliminar_gasto.html', {'gasto': gasto})


@login_required
def generar_gasto_siguiente(request, pk):
    gasto_original = get_object_or_404(Gasto, pk=pk, usuario=request.user)
    
    if gasto_original.periodicidad == 'mensual':
        nueva_fecha = (gasto_original.fecha_vencimiento or gasto_original.fecha) + relativedelta(months=1)
    elif gasto_original.periodicidad == 'bimestral':
        nueva_fecha = (gasto_original.fecha_vencimiento or gasto_original.fecha) + relativedelta(months=2)
    else:
        nueva_fecha = (gasto_original.fecha_vencimiento or gasto_original.fecha) + relativedelta(months=1)
    
    nuevo_gasto = Gasto.objects.create(
        usuario=request.user,
        categoria=gasto_original.categoria,
        nombre=gasto_original.nombre,
        monto=gasto_original.monto,
        fecha=nueva_fecha,
        fecha_vencimiento=nueva_fecha,
        forma_pago=gasto_original.forma_pago,
        estado='pendiente',
        es_recurrente=gasto_original.es_recurrente,
        pago_automatico=gasto_original.pago_automatico,
        periodicidad=gasto_original.periodicidad,
        tipo_gasto=gasto_original.tipo_gasto,
        meses_a_generar=1,
        observaciones=f'Generado desde gasto {gasto_original.id}'
    )
    
    messages.success(request, f'✅ Gasto generado - Vence: {nueva_fecha.strftime("%d/%m/%Y")}')
    return redirect('lista_gastos')


# ============ RESUMENES DE GASTOS ============

@login_required
def resumen_gastos_mensual(request, año=None, mes=None):
    actualizar_gastos_vencidos()
    if not año:
        año = datetime.now().year
    if not mes:
        mes = datetime.now().month
    
    año = int(año)
    mes = int(mes)
    
    gastos = Gasto.objects.filter(
        usuario=request.user,
        fecha__year=año,
        fecha__month=mes
    ).order_by('fecha_vencimiento', 'fecha')
    
    totales = gastos.aggregate(
        total=Sum('monto'),
        pendientes=Sum('monto', filter=Q(estado='pendiente')),
        pagados=Sum('monto', filter=Q(estado='pagado'))
    )
    
    context = {
        'gastos': gastos,
        'totales': totales,
        'año': año,
        'mes': mes,
        'nombre_mes': calendar.month_name[mes],
        'meses': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'años': range(2024, datetime.now().year + 2),
    }
    return render(request, 'finances/resumen_gastos_mensual.html', context)


@login_required
def resumen_gastos_anual(request, año=None):
    actualizar_gastos_vencidos()
    if not año:
        año = datetime.now().year
    año = int(año)
    
    resumen_mensual = []
    for mes in range(1, 13):
        datos = Gasto.objects.filter(
            usuario=request.user,
            fecha__year=año,
            fecha__month=mes
        ).aggregate(
            total=Sum('monto'),
            pendientes=Sum('monto', filter=Q(estado='pendiente')),
            pagados=Sum('monto', filter=Q(estado='pagado'))
        )
        resumen_mensual.append({
            'mes': mes,
            'nombre': calendar.month_name[mes],
            'total': datos['total'] or 0,
            'pendientes': datos['pendientes'] or 0,
            'pagados': datos['pagados'] or 0,
        })
    
    totales = Gasto.objects.filter(
        usuario=request.user,
        fecha__year=año
    ).aggregate(
        total=Sum('monto'),
        pendientes=Sum('monto', filter=Q(estado='pendiente')),
        pagados=Sum('monto', filter=Q(estado='pagado'))
    )
    
    context = {
        'resumen_mensual': resumen_mensual,
        'totales': totales,
        'año': año,
        'años': range(2024, datetime.now().year + 2),
    }
    return render(request, 'finances/resumen_gastos_anual.html', context)


# ============ RESUMEN GENERAL ============

@login_required
def resumen_general_mensual(request, año=None, mes=None):
    actualizar_cobros_vencidos()
    actualizar_gastos_vencidos()
    if not año:
        año = datetime.now().year
    if not mes:
        mes = datetime.now().month
    
    año = int(año)
    mes = int(mes)
    
    cobros = Cobro.objects.filter(
        usuario=request.user,
        fecha_vencimiento__year=año,
        fecha_vencimiento__month=mes
    )
    total_cobrado = cobros.aggregate(total=Sum('monto_pagado'))['total'] or 0
    total_a_cobrar = cobros.aggregate(total=Sum('monto_total'))['total'] or 0
    pendiente_cobros = cobros.aggregate(total=Sum('saldo'))['total'] or 0
    
    gastos = Gasto.objects.filter(
        usuario=request.user,
        fecha__year=año,
        fecha__month=mes
    )
    total_gastos = gastos.aggregate(total=Sum('monto'))['total'] or 0
    gastos_pagados = gastos.filter(estado='pagado').aggregate(total=Sum('monto'))['total'] or 0
    gastos_pendientes = gastos.filter(estado='pendiente').aggregate(total=Sum('monto'))['total'] or 0
    
    balance = total_cobrado - total_gastos
    
    context = {
        'total_cobrado': total_cobrado,
        'total_a_cobrar': total_a_cobrar,
        'pendiente_cobros': pendiente_cobros,
        'total_gastos': total_gastos,
        'gastos_pagados': gastos_pagados,
        'gastos_pendientes': gastos_pendientes,
        'balance': balance,
        'año': año,
        'mes': mes,
        'nombre_mes': calendar.month_name[mes],
        'meses': [(i, calendar.month_name[i]) for i in range(1, 13)],
        'años': range(2024, datetime.now().year + 2),
    }
    return render(request, 'finances/resumen_general.html', context)


@login_required
def resumen_general_anual(request, año=None):
    actualizar_cobros_vencidos()
    actualizar_gastos_vencidos()
    if not año:
        año = datetime.now().year
    año = int(año)
    
    resumen_mensual = []
    for mes in range(1, 13):
        cobros_mes = Cobro.objects.filter(
            usuario=request.user,
            fecha_vencimiento__year=año,
            fecha_vencimiento__month=mes
        )
        cobrado = cobros_mes.aggregate(total=Sum('monto_pagado'))['total'] or 0
        a_cobrar = cobros_mes.aggregate(total=Sum('monto_total'))['total'] or 0
        
        gastos_mes = Gasto.objects.filter(
            usuario=request.user,
            fecha__year=año,
            fecha__month=mes
        )
        gastos_total = gastos_mes.aggregate(total=Sum('monto'))['total'] or 0
        
        resumen_mensual.append({
            'mes': mes,
            'nombre': calendar.month_name[mes],
            'cobrado': cobrado,
            'a_cobrar': a_cobrar,
            'gastos': gastos_total,
            'balance': cobrado - gastos_total,
        })
    
    total_cobrado_año = Cobro.objects.filter(
        usuario=request.user,
        fecha_vencimiento__year=año
    ).aggregate(total=Sum('monto_pagado'))['total'] or 0
    
    total_gastos_año = Gasto.objects.filter(
        usuario=request.user,
        fecha__year=año
    ).aggregate(total=Sum('monto'))['total'] or 0
    
    context = {
        'resumen_mensual': resumen_mensual,
        'total_cobrado_año': total_cobrado_año,
        'total_gastos_año': total_gastos_año,
        'balance_anual': total_cobrado_año - total_gastos_año,
        'año': año,
        'años': range(2024, datetime.now().year + 2),
    }
    return render(request, 'finances/resumen_general_anual.html', context)


# ============ CLIENTES ============

@login_required
def crear_cliente_ajax(request):
    if request.method == 'POST':
        cliente = Cliente.objects.create(
            usuario=request.user,
            nombre=request.POST.get('nombre'),
            nombre_contacto=request.POST.get('nombre_contacto', ''),
            email=request.POST.get('email', ''),
            telefono=request.POST.get('telefono', ''),
            direccion=request.POST.get('direccion', ''),
            ciudad=request.POST.get('ciudad', ''),
            provincia=request.POST.get('provincia', ''),
            cuit=request.POST.get('cuit', ''),
            sistema=request.POST.get('sistema', ''),
            plan=request.POST.get('plan', ''),
            fecha_inicio=request.POST.get('fecha_inicio') or None,
            notas=request.POST.get('notas', ''),
        )
        return JsonResponse({'success': True, 'id': cliente.id, 'nombre': cliente.nombre})
    return JsonResponse({'success': False})


@login_required
def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk, usuario=request.user)
    if request.method == 'POST':
        cliente.nombre = request.POST.get('nombre')
        cliente.nombre_contacto = request.POST.get('nombre_contacto', '')
        cliente.email = request.POST.get('email', '')
        cliente.telefono = request.POST.get('telefono', '')
        cliente.direccion = request.POST.get('direccion', '')
        cliente.ciudad = request.POST.get('ciudad', '')
        cliente.provincia = request.POST.get('provincia', '')
        cliente.cuit = request.POST.get('cuit', '')
        cliente.sistema = request.POST.get('sistema', '')
        cliente.plan = request.POST.get('plan', '')
        cliente.fecha_inicio = request.POST.get('fecha_inicio') or None
        cliente.notas = request.POST.get('notas', '')
        cliente.save()
        messages.success(request, '✅ Cliente actualizado')
        return redirect('dashboard')
    return render(request, 'finances/form_cliente.html', {'cliente': cliente})


# ============ OTROS ============

@login_required
def notificaciones_lista(request):
    """Lista de notificaciones del usuario"""
    # Obtener notificaciones de cobros del usuario
    notificaciones = Notificacion.objects.filter(
        cobro__usuario=request.user
    ).order_by('-fecha_creacion')
    
    context = {
        'notificaciones': notificaciones,
        'total_no_leidas': notificaciones.filter(leida=False).count(),
    }
    return render(request, 'finances/notificaciones.html', context)


@login_required
def marcar_notificacion_leida(request, pk):
    """Marcar una notificación como leída"""
    notif = get_object_or_404(Notificacion, pk=pk)
    notif.leida = True
    notif.save()
    return redirect('notificaciones')


@login_required
def marcar_todas_leidas(request):
    """Marcar todas como leídas"""
    Notificacion.objects.filter(
        cobro__usuario=request.user,
        leida=False
    ).update(leida=True)
    messages.success(request, '✅ Todas las notificaciones marcadas como leídas')
    return redirect('notificaciones')


@login_required
def exportar_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cobros"
    ws.append(['Cliente', 'Sistema', 'Plan', 'Monto Total', 'Pagado', 'Saldo', 'Vencimiento', 'Estado'])
    for c in Cobro.objects.filter(usuario=request.user):
        ws.append([c.nombre_cliente, c.sistema, c.plan, float(c.monto_total),
                  float(c.monto_pagado), float(c.saldo), str(c.fecha_vencimiento), c.get_estado_display()])
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    response = HttpResponse(output.read(),
                          content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=cobros.xlsx'
    return response

def crear_notificaciones_proximas():
    """Crea notificaciones para cobros que vencen en los próximos 3 días"""
    hoy = hoy_local()
    fecha_limite = hoy + timedelta(days=3)
    
    cobros_proximos = Cobro.objects.filter(
        estado__in=['pendiente', 'parcial'],
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=fecha_limite
    )
    
    for cobro in cobros_proximos:
        dias = (cobro.fecha_vencimiento - hoy).days
        Notificacion.objects.get_or_create(
            cobro=cobro,
            tipo='cobro_proximo',
            fecha_creacion__date=hoy,
            defaults={
                'titulo': f'📅 Próximo vencimiento: {cobro.nombre_cliente}',
                'mensaje': f'El cobro de {cobro.nombre_cliente} por ${cobro.monto_total:,.2f} vence en {dias} día(s) ({cobro.fecha_vencimiento.strftime("%d/%m/%Y")}).'
            }
        )

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import mm
import os
from django.conf import settings

@login_required
def generar_comprobante_pdf(request, pk):
    """Genera un comprobante de pago en PDF"""
    cobro = get_object_or_404(Cobro, pk=pk, usuario=request.user)
    
    # Crear respuesta HTTP con PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="comprobante_{cobro.nombre_cliente}_{cobro.id}.pdf"'
    
    # Crear documento
    doc = SimpleDocTemplate(response, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Título
    title_style = ParagraphStyle('Title', fontSize=20, alignment=1, spaceAfter=10)
    elements.append(Paragraph("COMPROBANTE DE PAGO", title_style))
    elements.append(Spacer(1, 10))
    
    # Datos del emisor
    elements.append(Paragraph(f"<b>Emisor:</b> {request.user.username}", styles['Normal']))
    elements.append(Paragraph(f"<b>Fecha:</b> {hoy_local().strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 15))
    
    # Datos del cliente
    elements.append(Paragraph("<b>DATOS DEL CLIENTE</b>", styles['Heading2']))
    data_cliente = [
        ['Cliente:', cobro.nombre_cliente],
        ['Sistema:', cobro.sistema or '-'],
        ['Plan:', cobro.plan or '-'],
    ]
    
    if cobro.cliente:
        data_cliente.append(['Contacto:', cobro.cliente.nombre_contacto or '-'])
        data_cliente.append(['Teléfono:', cobro.cliente.telefono or '-'])
        data_cliente.append(['Email:', cobro.cliente.email or '-'])
    
    t_cliente = Table(data_cliente, colWidths=[80, 300])
    t_cliente.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_cliente)
    elements.append(Spacer(1, 15))
    
    # Datos del cobro
    elements.append(Paragraph("<b>DETALLE DEL PAGO</b>", styles['Heading2']))
    
    data_pago = [
        ['Concepto', 'Monto'],
        ['Monto Total', f'${cobro.monto_total:,.2f}'],
        ['Monto Pagado', f'${cobro.monto_pagado:,.2f}'],
        ['Saldo Pendiente', f'${cobro.saldo:,.2f}'],
        ['Estado', cobro.get_estado_display()],
        ['Forma de Pago', cobro.get_forma_pago_display()],
        ['Fecha de Vencimiento', cobro.fecha_vencimiento.strftime('%d/%m/%Y')],
    ]
    
    if cobro.fecha_pago:
        data_pago.append(['Fecha de Pago', cobro.fecha_pago.strftime('%d/%m/%Y')])
    
    t_pago = Table(data_pago, colWidths=[120, 260])
    t_pago.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    elements.append(t_pago)
    elements.append(Spacer(1, 20))
    
    # Observaciones
    if cobro.observaciones:
        elements.append(Paragraph("<b>Observaciones:</b>", styles['Normal']))
        elements.append(Paragraph(cobro.observaciones, styles['Normal']))
        elements.append(Spacer(1, 15))
    
    # Pie
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("_" * 60, styles['Normal']))
    elements.append(Paragraph("Firma del responsable", styles['Normal']))
    
    doc.build(elements)
    return response

