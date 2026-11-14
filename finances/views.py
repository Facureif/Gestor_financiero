from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
import calendar
import json

from dateutil.relativedelta import relativedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Q, Count
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required

import openpyxl
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import mm

from .models import Categoria, Cliente, Cobro, Gasto, ItemCobro, ItemGasto, Notificacion

# Diccionario para los meses en español
MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

# ============ FUNCIONES HELPER ============

def hoy_local():
    """Devuelve la fecha actual en la zona horaria local"""
    return timezone.localtime(timezone.now()).date()


def actualizar_estados(request=None):
    """Actualiza estados y notificaciones solo para el usuario actual (o todos si no hay request)"""
    hoy = hoy_local()

    if request is not None:
        cobros_qs = Cobro.objects.filter(usuario=request.user)
        gastos_qs = Gasto.objects.filter(usuario=request.user)
    else:
        cobros_qs = Cobro.objects.all()
        gastos_qs = Gasto.objects.all()

    # --- Cobros vencidos ---
    cobros_vencidos = cobros_qs.filter(
        estado__in=['pendiente', 'parcial'],
        fecha_vencimiento__lt=hoy
    )
    for cobro in cobros_vencidos:
        Notificacion.objects.get_or_create(
            cobro=cobro,
            tipo='cobro_vencido',
            defaults={
                'titulo': f'⚠️ Cobro vencido: {cobro.nombre_cliente}',
                'mensaje': (
                    f'El cobro de {cobro.nombre_cliente} por '
                    f'${cobro.saldo:,.2f} venció el '
                    f'{cobro.fecha_vencimiento.strftime("%d/%m/%Y")}.'
                ),
            }
        )
    cobros_vencidos.update(estado='vencido')

    # --- Gastos vencidos ---
    gastos_qs.filter(
        estado='pendiente',
        fecha_vencimiento__lt=hoy
    ).update(estado='vencido')

    # --- Cobros próximos (3 días) ---
    fecha_limite = hoy + timedelta(days=3)
    cobros_proximos = cobros_qs.filter(
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
                'mensaje': (
                    f'El cobro de {cobro.nombre_cliente} por '
                    f'${cobro.monto_total:,.2f} vence en {dias} día(s) '
                    f'({cobro.fecha_vencimiento.strftime("%d/%m/%Y")}).'
                ),
            }
        )


def _filtro_notif_usuario(user):
    """Q object para filtrar notificaciones del usuario (por cobro o por gasto)"""
    return Q(cobro__usuario=user) | Q(gasto__usuario=user)


# ============ DASHBOARD ============

@login_required
def dashboard(request):
    actualizar_estados(request)
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

    if total_a_cobrar > 0:
        porcentaje_cobranza = float(total_cobrado) / float(total_a_cobrar) * 100
        porcentaje_pendiente = 100 - porcentaje_cobranza
    else:
        porcentaje_cobranza = 0
        porcentaje_pendiente = 0

    proximos_cobros = Cobro.objects.filter(
        usuario=request.user,
        estado__in=['pendiente', 'parcial'],
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=hoy + timedelta(days=14)
    ).select_related('cliente').order_by('fecha_vencimiento')

    cobros_vencidos = Cobro.objects.filter(
        usuario=request.user,
        estado='vencido'
    ).select_related('cliente').order_by('fecha_vencimiento')[:10]

    ultimos_cobros = Cobro.objects.filter(
        usuario=request.user
    ).select_related('cliente').order_by('-actualizado')[:5]

    # ----- GASTOS -----
    gastos_mes = Gasto.objects.filter(
        usuario=request.user,
        fecha__year=año_actual,
        fecha__month=mes_actual
    )
    total_gastos = gastos_mes.aggregate(total=Sum('monto'))['total'] or 0

    gastos_categoria = Gasto.objects.filter(
        usuario=request.user,
        fecha__year=año_actual,
        fecha__month=mes_actual,
        monto__isnull=False
    ).values('categoria__nombre', 'categoria__color').annotate(
        total=Sum('monto')
    ).order_by('-total')

    categorias_gastos_json = json.dumps([
        {'nombre': c['categoria__nombre'],
         'color': c['categoria__color'],
         'total': float(c['total'])}
        for c in gastos_categoria
    ])

    proximos_gastos = Gasto.objects.filter(
        usuario=request.user,
        estado='pendiente',
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=hoy + timedelta(days=14)
    ).select_related('categoria').order_by('fecha_vencimiento')

    balance = total_cobrado - total_gastos

    total_no_leidas = Notificacion.objects.filter(
        _filtro_notif_usuario(request.user),
        leida=False
    ).count()

    # ----- VENCIDOS (Cobros y Gastos) -----
    cobros_vencidos = Cobro.objects.filter(
        usuario=request.user, estado='vencido'
    ).select_related('cliente').order_by('fecha_vencimiento')[:5]  # Solo 5

    gastos_vencidos = Gasto.objects.filter(
        usuario=request.user, estado='vencido'
    ).select_related('categoria').order_by('fecha_vencimiento')[:5]  # Solo 5
    
    # Totales para mostrar en la tarjeta
    total_vencido_cobros = Cobro.objects.filter(usuario=request.user, estado='vencido').aggregate(total=Sum('saldo'))['total'] or 0
    total_vencido_gastos = Gasto.objects.filter(usuario=request.user, estado='vencido').aggregate(total=Sum('monto'))['total'] or 0

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
        'mes_actual': MESES_ES[mes_actual],
        'año_actual': año_actual,
        'cobros_vencidos': cobros_vencidos,
        'gastos_vencidos': gastos_vencidos,
        'total_vencido_cobros': total_vencido_cobros,
        'total_vencido_gastos': total_vencido_gastos,
    }
    return render(request, 'finances/dashboard.html', context)


# ============ COBROS ============

@login_required
def lista_cobros(request):
    actualizar_estados(request)
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
            cobros = cobros.filter(
                fecha_vencimiento__month=mes,
                fecha_vencimiento__year=año
            )
    elif año:
        año = int(año)
        cobros = cobros.filter(fecha_vencimiento__year=año)

    if estado:
        cobros = cobros.filter(estado=estado)

    if buscar:
        # FIX: Buscar en concepto y detalle en vez de sistema y plan
        cobros = cobros.filter(
            Q(nombre_cliente__icontains=buscar) |
            Q(concepto__icontains=buscar) |
            Q(detalle__icontains=buscar)
        )

    cobros = cobros.select_related('cliente').order_by('fecha_vencimiento')

    totales = cobros.aggregate(
        total=Sum('monto_total'),
        pagado=Sum('monto_pagado'),
        pendiente=Sum('saldo')
    )

    context = {
        'cobros': cobros,
        'totales': totales,
        'meses': [(i, MESES_ES[i]) for i in range(1, 13)],
        'años': range(2024, hoy.year + 2),
        'filtros': {
            'mes': int(mes) if mes else '',
            'año': int(año) if año else '',
            'estado': estado,
            'buscar': buscar,
        },
        'nombre_mes': MESES_ES[int(mes)] if mes else '',
        'año_actual': int(año) if año else hoy.year,
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
            if fecha_str:
                fecha_vencimiento = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            else:
                fecha_vencimiento = hoy_local()
            
            fecha_emision = hoy_local()

            cobro_base = Cobro.objects.create(
                usuario=request.user,
                cliente_id=cliente_id,
                nombre_cliente=request.POST.get('nombre_cliente'),
                concepto=request.POST.get('concepto', ''), 
                detalle=request.POST.get('detalle', ''),
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

            # Guardar los ítems (si vienen del formulario)
            descripciones = request.POST.getlist('item_descripcion[]')
            cantidades = request.POST.getlist('item_cantidad[]')
            precios = request.POST.getlist('item_precio[]')
            
            for i in range(len(descripciones)):
                if descripciones[i] and precios[i]: # Solo guarda si hay datos
                    ItemCobro.objects.create(
                        cobro=cobro_base,
                        descripcion=descripciones[i],
                        cantidad=Decimal(cantidades[i] or 1),
                        precio_unitario=Decimal(precios[i])
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
                        concepto=cobro_base.concepto,  # FIX
                        detalle=cobro_base.detalle,    # FIX
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
            cobro.concepto = request.POST.get('concepto', '')  
            cobro.detalle = request.POST.get('detalle', '') 
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

                if cobro.cliente_id:
                    filtro_cliente = Q(cliente_id=cobro.cliente_id)
                else:
                    filtro_cliente = Q(
                        cliente_id__isnull=True,
                        nombre_cliente=cobro.nombre_cliente
                    )

                siguientes = Cobro.objects.filter(
                    filtro_cliente,
                    usuario=request.user,
                    fecha_vencimiento__gt=cobro.fecha_vencimiento,
                    estado__in=['pendiente', 'parcial']
                )

                actualizados = 0
                for c in siguientes:
                    c.monto_total = nuevo_monto
                    c.monto_pagado = Decimal('0')
                    c.save()
                    actualizados += 1

                messages.success(
                    request,
                    f'✅ Cobro actualizado y {actualizados} siguientes ajustados'
                )
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
def cancelar_cobros_futuros(request, pk):
    cobro_base = get_object_or_404(Cobro, pk=pk, usuario=request.user)
    
    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'todos':
            # Buscamos todos los cobros del mismo cliente que sean de esta fecha en adelante
            cobros_a_cancelar = Cobro.objects.filter(
                usuario=request.user,
                cliente=cobro_base.cliente,
                fecha_vencimiento__gte=cobro_base.fecha_vencimiento,
                estado__in=['pendiente', 'parcial', 'vencido', 'programado']
            )
            cantidad = cobros_a_cancelar.count()
            cobros_a_cancelar.update(estado='cancelado')
            messages.success(request, f'✅ Se cancelaron {cantidad} cobros a partir de la fecha.')
            
        elif accion == 'uno':
            cobro_base.estado = 'cancelado'
            cobro_base.save()
            messages.success(request, '✅ Cobro cancelado.')
            
        return redirect('historial_cliente', slug=cobro_base.cliente.slug)

@login_required
def generar_cobro_siguiente(request, pk):
    cobro_original = get_object_or_404(Cobro, pk=pk, usuario=request.user)
    nueva_fecha = cobro_original.fecha_vencimiento + relativedelta(months=1)

    Cobro.objects.create(
        usuario=request.user,
        cliente=cobro_original.cliente,
        nombre_cliente=cobro_original.nombre_cliente,
        concepto=cobro_original.concepto,  # FIX
        detalle=cobro_original.detalle,    # FIX
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
        monto_str = request.POST.get('monto_pagado', '0').replace(',', '.')
        try:
            monto = Decimal(monto_str)
        except Exception:
            messages.error(request, '❌ Monto inválido')
            return redirect('registrar_pago', pk=pk)

        if monto <= 0:
            messages.error(request, '❌ El monto debe ser mayor a 0')
        elif monto > cobro.saldo:
            messages.error(request, f'❌ El monto no puede superar el saldo pendiente (${cobro.saldo:,.2f})')
        else:
            cobro.monto_pagado = cobro.monto_pagado + monto
            cobro.fecha_pago = hoy_local()

            if request.FILES.get('comprobante'):
                cobro.comprobante = request.FILES['comprobante']

            cobro.save()
            messages.success(request, f'✅ Pago de ${monto:,.2f} registrado')
            return redirect('lista_cobros')

    return render(request, 'finances/registrar_pago.html', {'cobro': cobro})

@login_required
def historial_cliente(request, slug):
    actualizar_estados(request)
    cliente = get_object_or_404(Cliente, slug=slug, usuario=request.user)
    hoy = hoy_local()

    # 1. Manejo del Año seleccionado
    año_actual = int(request.GET.get('año', hoy.year))
    
    # 2. Traemos todos los cobros de ESE año
    cobros_año = Cobro.objects.filter(
        usuario=request.user,
        cliente=cliente,
        fecha_vencimiento__year=año_actual
    ).select_related('cliente').order_by('fecha_vencimiento')

    # 3. Agrupamos por mes (1 al 12)
    historial_meses = {}
    for c in cobros_año:
        fecha = c.fecha_vencimiento or c.fecha_emision
        mes = fecha.month
        historial_meses.setdefault(mes, []).append(c)
    
    # Ordenamos los meses de Enero a Diciembre
    historial_ordenado = dict(sorted(historial_meses.items()))

    # 4. Navegación de años (para el selector)
    años_qs = Cobro.objects.filter(usuario=request.user, cliente=cliente).dates('fecha_vencimiento', 'year')
    años_disponibles = [d.year for d in años_qs]
    if hoy.year not in años_disponibles:
        años_disponibles.append(hoy.year)
    if not años_disponibles:
        años_disponibles = [hoy.year]
    años_disponibles = sorted(list(set(años_disponibles)))

    # 5. Totales Globales (de todos los años, para las tarjetas de arriba)
    todos_cobros = Cobro.objects.filter(usuario=request.user, cliente=cliente)
    
    total_cobrado = todos_cobros.aggregate(total=Sum('monto_pagado'))['total'] or 0
    cobros_pendientes = todos_cobros.filter(
        Q(fecha_vencimiento__lte=hoy) | Q(fecha_vencimiento__isnull=True),
        estado__in=['pendiente', 'parcial', 'vencido']
    )
    total_pendiente = cobros_pendientes.aggregate(total=Sum('saldo'))['total'] or 0
    
    cobros_futuros = todos_cobros.filter(
        fecha_vencimiento__gt=hoy,
        estado__in=['pendiente', 'parcial']
    )
    total_programado = cobros_futuros.aggregate(total=Sum('saldo'))['total'] or 0

    context = {
        'nombre': cliente.nombre,
        'cliente': cliente,
        'año_actual': año_actual,
        'prev_año': año_actual - 1,
        'next_año': año_actual + 1,
        'años_disponibles': años_disponibles,
        'historial_meses': historial_ordenado,
        'MESES_ES': MESES_ES,  # Para traducir el mes en el HTML
        'total_cobros': todos_cobros.count(),
        'total_cobrado': total_cobrado,
        'total_pendiente': total_pendiente,
        'total_programado': total_programado,
    }
    return render(request, 'finances/historial_cliente.html', context)


@login_required
def exportar_historial_excel(request, slug):
    cliente = get_object_or_404(Cliente, slug=slug, usuario=request.user)
    cobros = Cobro.objects.filter(usuario=request.user, cliente=cliente).order_by('fecha_vencimiento')
    hoy = hoy_local()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Historial"
    
    # Estilos para el Excel
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="3b82f6", end_color="3b82f6", fill_type="solid")
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    # Encabezado
    ws.append(['Cliente:', cliente.nombre])
    ws.append(['CUIT/CUIL:', cliente.cuit or '-'])
    ws.append(['Fecha de reporte:', hoy.strftime('%d/%m/%Y')])
    ws.append([])
    
    # Cabecera de tabla
    headers = ['Fecha', 'Concepto', 'Detalle', 'Total', 'Pagado', 'Saldo', 'Estado']
    ws.append(headers)
    
    # Aplicar estilo a la cabecera
    for cell in ws[5]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = border

    total_facturado = 0
    total_cobrado = 0
    total_pendiente = 0

    for c in cobros:
        fecha = c.fecha_vencimiento or c.fecha_emision
        
        # Calcular estados futuros
        estado_display = c.get_estado_display()
        if c.estado in ['pendiente', 'parcial'] and fecha > hoy:
            estado_display = 'Programado'

        ws.append([
            fecha.strftime('%d/%m/%Y'),
            c.concepto or '-',
            c.detalle or '-',
            float(c.monto_total),
            float(c.monto_pagado),
            float(c.saldo),
            estado_display
        ])
        
        total_facturado += float(c.monto_total)
        total_cobrado += float(c.monto_pagado)
        total_pendiente += float(c.saldo)

    # Fila de totales
    ws.append([])
    ws.append(['', '', 'TOTALES:', total_facturado, total_cobrado, total_pendiente, ''])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.border = border

    # Ajustar ancho de columnas
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 25
        
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=Historial_{cliente.nombre}.xlsx'
    return response


@login_required
def exportar_historial_pdf(request, slug):
    cliente = get_object_or_404(Cliente, slug=slug, usuario=request.user)
    cobros = Cobro.objects.filter(usuario=request.user, cliente=cliente).order_by('fecha_vencimiento')
    hoy = hoy_local()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Historial_{cliente.nombre}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=20*mm)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título y Cabecera
    elements.append(Paragraph(f"HISTORIAL DE CUENTA", styles['Title']))
    elements.append(Paragraph(f"<b>Cliente:</b> {cliente.nombre}", styles['Normal']))
    if cliente.cuit:
        elements.append(Paragraph(f"<b>CUIT/CUIL:</b> {cliente.cuit}", styles['Normal']))
    elements.append(Paragraph(f"<b>Fecha de emisión:</b> {hoy.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 15))
    
    # Tabla
    data = [['Fecha', 'Concepto', 'Detalle', 'Total', 'Pagado', 'Saldo', 'Estado']]
    
    total_facturado = 0
    total_cobrado = 0
    total_pendiente = 0

    for c in cobros:
        fecha = c.fecha_vencimiento or c.fecha_emision
        
        estado_display = c.get_estado_display()
        if c.estado in ['pendiente', 'parcial'] and fecha > hoy:
            estado_display = 'Programado'

        # Usamos Paragraph para que el texto no rompa la tabla
        data.append([
            fecha.strftime('%d/%m/%Y'),
            Paragraph(c.concepto or '-', styles['Normal']),
            Paragraph(c.detalle or '-', styles['Normal']),
            f'${c.monto_total:,.2f}',
            f'${c.monto_pagado:,.2f}',
            f'${c.saldo:,.2f}',
            estado_display
        ])
        
        total_facturado += float(c.monto_total)
        total_cobrado += float(c.monto_pagado)
        total_pendiente += float(c.saldo)

    # Fila de totales
    data.append(['', '', 'TOTALES:', f'${total_facturado:,.2f}', f'${total_cobrado:,.2f}', f'${total_pendiente:,.2f}', ''])

    t = Table(data, colWidths=[60, 120, 120, 65, 65, 65, 55])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (3, 0), (5, -1), 'RIGHT'), # Alinear montos a la derecha
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Estilo para la última fila (Totales)
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8f9fa')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    doc.build(elements)
    
    return response


@login_required
def generar_comprobante_pdf(request, pk):
    """Genera un comprobante de pago en PDF"""
    cobro = get_object_or_404(Cobro, pk=pk, usuario=request.user)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="comprobante_{cobro.nombre_cliente}_{cobro.id}.pdf"'
    )

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm
    )
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', fontSize=20, alignment=1, spaceAfter=10)
    elements.append(Paragraph("COMPROBANTE DE PAGO", title_style))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"<b>Emisor:</b> {request.user.username}", styles['Normal']))
    elements.append(Paragraph(f"<b>Fecha de emisión:</b> {hoy_local().strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("<b>DATOS DEL CLIENTE</b>", styles['Heading2']))
    
    data_cliente = [
        ['Cliente:', cobro.nombre_cliente],
        ['Concepto:', cobro.concepto or '-'],
        ['Detalle:', cobro.detalle or '-'],
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

    elements.append(Paragraph("<b>DETALLE DEL PAGO</b>", styles['Heading2']))
    
    # Si es futuro, lo mostramos como Programado
    estado_display = cobro.get_estado_display()
    if cobro.estado in ['pendiente', 'parcial'] and cobro.fecha_vencimiento and cobro.fecha_vencimiento > hoy_local():
        estado_display = 'Programado'

    data_pago = [
        ['Concepto', 'Monto'],
        ['Monto Total', f'${cobro.monto_total:,.2f}'],
        ['Monto Pagado', f'${cobro.monto_pagado:,.2f}'],
        ['Saldo Pendiente', f'${cobro.saldo:,.2f}'],
        ['Estado', estado_display],
        ['Forma de Pago', cobro.get_forma_pago_display()],
        ['Fecha de Vencimiento', cobro.fecha_vencimiento.strftime('%d/%m/%Y') if cobro.fecha_vencimiento else '-'],
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
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    elements.append(t_pago)
    elements.append(Spacer(1, 20))

    if cobro.observaciones:
        elements.append(Paragraph("<b>Observaciones:</b>", styles['Normal']))
        elements.append(Paragraph(cobro.observaciones, styles['Normal']))
        elements.append(Spacer(1, 15))

    elements.append(Spacer(1, 30))
    elements.append(Paragraph("_" * 60, styles['Normal']))
    elements.append(Paragraph("Firma del responsable", styles['Normal']))

    doc.build(elements)
    return response

# ============ RESUMENES DE COBROS ============
@login_required
def resumen_cobros_mensual(request, año=None, mes=None):
    actualizar_estados(request)

    # FIX: Buscar el mes y año en la URL (GET), si no están, usar los actuales
    if not año:
        año = request.GET.get('año', datetime.now().year)
    if not mes:
        mes = request.GET.get('mes', datetime.now().month)

    año = int(año)
    mes = int(mes)

    # --- COBROS DEL MES ---
    cobros = Cobro.objects.filter(
        usuario=request.user,
        fecha_vencimiento__year=año,
        fecha_vencimiento__month=mes
    ).select_related('cliente').order_by('fecha_vencimiento')

    # --- GASTOS DEL MES ---
    gastos = Gasto.objects.filter(
        usuario=request.user,
        fecha__year=año,
        fecha__month=mes
    ).select_related('categoria').order_by('fecha')

    # --- CÁLCULOS ---
    total_cobrado = cobros.aggregate(total=Sum('monto_pagado'))['total'] or 0
    total_gastos = gastos.aggregate(total=Sum('monto'))['total'] or 0
    balance = total_cobrado - total_gastos

    # Vencidos
    cobros_vencidos = cobros.filter(estado='vencido')
    gastos_vencidos = gastos.filter(estado='vencido')

    context = {
        'cobros': cobros,
        'gastos': gastos,
        'total_cobrado': total_cobrado,
        'total_gastos': total_gastos,
        'balance': balance,
        'hay_vencidos': cobros_vencidos.exists() or gastos_vencidos.exists(),
        'cobros_vencidos': cobros_vencidos,
        'gastos_vencidos': gastos_vencidos,
        'año': año,
        'mes': mes,
        'nombre_mes': MESES_ES[mes],
        'meses': [(i, MESES_ES[i]) for i in range(1, 13)],
        'años': range(2024, datetime.now().year + 2),
    }
    return render(request, 'finances/resumen_mensual.html', context)


@login_required
def exportar_balance_excel(request, año, mes):
    año = int(año)
    mes = int(mes)
    periodo = f"{MESES_ES[mes]} {año}"
    hoy = hoy_local()

    cobros = Cobro.objects.filter(usuario=request.user, fecha_vencimiento__year=año, fecha_vencimiento__month=mes)
    gastos = Gasto.objects.filter(usuario=request.user, fecha__year=año, fecha__month=mes)

    total_cobrado = cobros.aggregate(total=Sum('monto_pagado'))['total'] or 0
    total_gastos = gastos.aggregate(total=Sum('monto'))['total'] or 0
    balance = total_cobrado - total_gastos

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance"

    from openpyxl.styles import Font, PatternFill
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="3b82f6", end_color="3b82f6", fill_type="solid")

    ws.append([f'BALANCE MENSUAL - {periodo}'])
    ws.append(['Fecha de Emisión:', hoy.strftime('%d/%m/%Y')])
    ws.append([])
    
    ws.append(['INGRESOS (COBROS)'])
    ws.append(['Fecha', 'Cliente', 'Concepto', 'Monto Pagado'])
    for c in cobros:
        ws.append([c.fecha_vencimiento.strftime('%d/%m/%Y') if c.fecha_vencimiento else '-', c.nombre_cliente, c.concepto, float(c.monto_pagado)])
    
    ws.append([])
    ws.append(['EGRESOS (GASTOS)'])
    ws.append(['Fecha', 'Concepto', 'Categoría', 'Monto'])
    for g in gastos:
        ws.append([g.fecha.strftime('%d/%m/%Y'), g.nombre, g.categoria.nombre, float(g.monto) if g.monto else 0])

    ws.append([])
    ws.append(['', '', 'TOTAL COBRADO:', total_cobrado])
    ws.append(['', '', 'TOTAL GASTOS:', total_gastos])
    ws.append(['', '', 'BALANCE NETO:', balance])
    
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)

    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 25

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Balance_{periodo.replace(" ", "_")}.xlsx"'
    return response


@login_required
def exportar_balance_pdf(request, año, mes):
    año = int(año)
    mes = int(mes)
    periodo = f"{MESES_ES[mes]} {año}"
    hoy = hoy_local()

    cobros = Cobro.objects.filter(usuario=request.user, fecha_vencimiento__year=año, fecha_vencimiento__month=mes)
    gastos = Gasto.objects.filter(usuario=request.user, fecha__year=año, fecha__month=mes)

    total_cobrado = cobros.aggregate(total=Sum('monto_pagado'))['total'] or 0
    total_gastos = gastos.aggregate(total=Sum('monto'))['total'] or 0
    balance = total_cobrado - total_gastos

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Balance_{periodo.replace(" ", "_")}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=20*mm)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"BALANCE MENSUAL - {periodo}", styles['Title']))
    elements.append(Paragraph(f"<b>Fecha de emisión:</b> {hoy.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("<b>RESUMEN</b>", styles['Heading2']))
    data_resumen = [
        ['Total Cobrado (Ingresos):', f'${total_cobrado:,.2f}'],
        ['Total Gastos (Egresos):', f'${total_gastos:,.2f}'],
        ['BALANCE NETO:', f'${balance:,.2f}']
    ]
    t_res = Table(data_resumen, colWidths=[150, 100])
    t_res.setStyle(TableStyle([
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 2), (-1, 2), colors.HexColor('#3b82f6') if balance >= 0 else colors.HexColor('#ef4444')),
    ]))
    elements.append(t_res)
    elements.append(Spacer(1, 15))

    elements.append(Paragraph("<b>DETALLE DE COBROS</b>", styles['Heading2']))
    data_c = [['Fecha', 'Cliente', 'Concepto', 'Pagado']]
    for c in cobros:
        data_c.append([c.fecha_vencimiento.strftime('%d/%m/%Y') if c.fecha_vencimiento else '-', c.nombre_cliente, Paragraph(c.concepto or '-', styles['Normal']), f'${c.monto_pagado:,.2f}'])
    t_c = Table(data_c, colWidths=[60, 130, 140, 70])
    t_c.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.grey), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white)]))
    elements.append(t_c)
    
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("<b>DETALLE DE GASTOS</b>", styles['Heading2']))
    data_g = [['Fecha', 'Concepto', 'Categoría', 'Monto']]
    for g in gastos:
        data_g.append([g.fecha.strftime('%d/%m/%Y'), Paragraph(g.nombre, styles['Normal']), g.categoria.nombre, f'${g.monto:,.2f}' if g.monto else 'S/M'])
    t_g = Table(data_g, colWidths=[60, 150, 100, 70])
    t_g.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.grey), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white)]))
    elements.append(t_g)

    doc.build(elements)
    return response


@login_required
def ajustar_precio_desde(request, pk):
    cobro_inicial = get_object_or_404(Cobro, pk=pk, usuario=request.user)

    if request.method == 'POST':
        nuevo_monto = Decimal(str(request.POST.get('nuevo_monto', 0) or 0))

        cobro_inicial.monto_total = nuevo_monto
        cobro_inicial.save()

        if cobro_inicial.cliente_id:
            filtro_cliente = Q(cliente_id=cobro_inicial.cliente_id)
        else:
            filtro_cliente = Q(
                cliente_id__isnull=True,
                nombre_cliente=cobro_inicial.nombre_cliente
            )

        siguientes = Cobro.objects.filter(
            filtro_cliente,
            usuario=request.user,
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
    actualizar_estados(request)
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

    gastos = gastos.select_related('categoria').order_by(
        'estado', 'fecha_vencimiento', 'fecha'
    )

    context = {
        'gastos': gastos,
        'nombre_mes': MESES_ES[int(mes)] if mes else '',
        'meses': [(i, MESES_ES[i]) for i in range(1, 13)],
        'años': range(2024, hoy.year + 2),
        'filtros': {
            'mes': int(mes) if mes else '',
            'año': int(año) if año else '',
            'estado': estado,
            'buscar': buscar,
        },
    }
    return render(request, 'finances/lista_gastos.html', context)


def asegurar_categorias_gasto(user):
    """Garantiza que el usuario tenga todas las categorías por defecto sin duplicar"""
    from usuarios.views import crear_categorias_default
    crear_categorias_default(user)
    return Categoria.objects.filter(usuario=user, activo=True, tipo='gasto')


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
            fecha_vencimiento = (
                datetime.strptime(vencimiento_str, '%Y-%m-%d').date()
                if vencimiento_str else None
            )

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
            
            # Guardar los ítems (si vienen del formulario)
            descripciones = request.POST.getlist('item_descripcion[]')
            cantidades = request.POST.getlist('item_cantidad[]')
            precios = request.POST.getlist('item_precio[]')
            
            for i in range(len(descripciones)):
                if descripciones[i] and precios[i]: # Solo guarda si hay datos
                    ItemGasto.objects.create(
                        gasto=gasto_base,
                        descripcion=descripciones[i],
                        cantidad=Decimal(cantidades[i] or 1),
                        precio_unitario=Decimal(precios[i])
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

    categorias = asegurar_categorias_gasto(request.user)
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
        gasto.descripcion = request.POST.get('descripcion', '')
        gasto.monto = request.POST.get('monto') or None
        gasto.tipo_gasto = request.POST.get('tipo_gasto', 'fijo')
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

    categorias = asegurar_categorias_gasto(request.user)
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

    Gasto.objects.create(
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
    actualizar_estados(request)

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
    ).select_related('categoria').order_by('fecha_vencimiento', 'fecha')

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
        'nombre_mes': MESES_ES[mes],
        'meses': [(i, MESES_ES[i]) for i in range(1, 13)],
        'años': range(2024, datetime.now().year + 2),
    }
    return render(request, 'finances/resumen_gastos_mensual.html', context)


@login_required
def resumen_gastos_anual(request, año=None):
    actualizar_estados(request)

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
            'nombre': MESES_ES[mes],
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
def resumen_general_anual(request, año=None):
    actualizar_estados(request)

    # FIX: Buscar el año en la URL (GET), si no está, usar el actual
    if not año:
        año = request.GET.get('año', datetime.now().year)
    
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

        # Calcular efectividad de cobranza del mes
        efectividad = (float(cobrado) / float(a_cobrar) * 100) if a_cobrar > 0 else 0

        resumen_mensual.append({
            'mes': mes,
            'nombre': MESES_ES[mes],
            'cobrado': cobrado,
            'a_cobrar': a_cobrar,
            'gastos': gastos_total,
            'balance': cobrado - gastos_total,
            'efectividad': efectividad,
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
def lista_clientes(request):
    buscar = (request.GET.get('buscar') or '').strip()
    hoy = hoy_local()

    # Filtros lógicos para reutilizar
    futuros_q = Q(
        cobros__usuario=request.user,
        cobros__fecha_vencimiento__gt=hoy,
        cobros__estado__in=['pendiente', 'parcial']
    )
    actuales_q = Q(cobros__usuario=request.user) & ~futuros_q

    clientes = Cliente.objects.filter(usuario=request.user).annotate(
        total_cobros=Count('cobros', filter=Q(cobros__usuario=request.user)),
        
        # Conteo separado
        cobros_actuales=Count('cobros', filter=actuales_q),
        cobros_futuros=Count('cobros', filter=futuros_q),
        
        # Saldo separado (ya lo teníamos)
        saldo_actual=Sum(
            'cobros__saldo',
            filter=Q(
                Q(cobros__fecha_vencimiento__lte=hoy) | Q(cobros__fecha_vencimiento__isnull=True),
                cobros__usuario=request.user,
                cobros__estado__in=['pendiente', 'parcial', 'vencido']
            )
        ),
        saldo_futuro=Sum(
            'cobros__saldo',
            filter=futuros_q
        )
    )

    if buscar:
        clientes = clientes.filter(
            Q(nombre__icontains=buscar) |
            Q(nombre_contacto__icontains=buscar) |
            Q(email__icontains=buscar) |
            Q(telefono__icontains=buscar) |
            Q(sistema__icontains=buscar) |
            Q(plan__icontains=buscar)
        )

    clientes = clientes.order_by('nombre')

    return render(request, 'finances/lista_clientes.html', {
        'clientes': clientes,
        'buscar': buscar,
    })

@login_required
def crear_cliente(request):
    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        if not nombre:
            messages.error(request, '❌ El nombre es obligatorio')
        else:
            try:
                cliente = Cliente.objects.create(
                    usuario=request.user,
                    nombre=nombre,
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
                messages.success(request, f'✅ Cliente "{cliente.nombre}" creado')
                return redirect('lista_clientes')
            except Exception as e:
                messages.error(request, f'❌ Error: {e}')

    return render(request, 'finances/form_cliente.html')


@login_required
def crear_cliente_ajax(request):
    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        if not nombre:
            return JsonResponse({'success': False, 'error': 'El nombre es obligatorio'})
        try:
            cliente = Cliente.objects.create(
                usuario=request.user,
                nombre=nombre,
                nombre_contacto=request.POST.get('nombre_contacto', ''),
                email=request.POST.get('email', ''),
                telefono=request.POST.get('telefono', ''),
                sistema=request.POST.get('sistema', ''),
                plan=request.POST.get('plan', ''),
            )
            return JsonResponse({'success': True, 'id': cliente.id, 'nombre': cliente.nombre})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required
def crear_categoria_ajax(request):
    if request.method == 'POST':
        nombre = (request.POST.get('nombre') or '').strip()
        icono = request.POST.get('icono') or '📦'
        
        if not nombre:
            return JsonResponse({'success': False, 'error': 'El nombre es obligatorio'})
            
        try:
            categoria, created = Categoria.objects.get_or_create(
                usuario=request.user,
                nombre=nombre,
                defaults={
                    'tipo': 'gasto',
                    'color': '#3498db',
                    'icono': icono,
                    'activo': True
                }
            )
            if not created:
                return JsonResponse({'success': False, 'error': 'Ya tenés una categoría con ese nombre'})
                
            return JsonResponse({
                'success': True, 
                'id': categoria.id, 
                'nombre': categoria.nombre,
                'icono': categoria.icono
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


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
        return redirect('lista_clientes')
    return render(request, 'finances/form_cliente.html', {'cliente': cliente})


# ============ OTROS ============

@login_required
def notificaciones_lista(request):
    # FIX: Filtramos para que SOLO traiga las que NO fueron leídas
    notificaciones = Notificacion.objects.filter(
        _filtro_notif_usuario(request.user),
        leida=False
    ).order_by('-fecha_creacion')

    context = {
        'notificaciones': notificaciones,
        'total_no_leidas': notificaciones.count(),
    }
    return render(request, 'finances/notificaciones.html', context)


@login_required
def marcar_notificacion_leida(request, pk):
    notif = get_object_or_404(
        Notificacion,
        _filtro_notif_usuario(request.user),
        pk=pk
    )
    notif.leida = True
    notif.save()
    
    # FIX: Si viene por JS (AJAX), devolvemos un OK en vez de recargar la página
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
        
    return redirect('notificaciones')


@login_required
def marcar_todas_leidas(request):
    Notificacion.objects.filter(
        _filtro_notif_usuario(request.user),
        leida=False
    ).update(leida=True)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
        
    messages.success(request, '✅ Todas las notificaciones marcadas como leídas')
    return redirect('notificaciones')


@login_required
def exportar_cobros_excel(request):
    hoy = hoy_local()
    mes = request.GET.get('mes', hoy.month)
    año = request.GET.get('año', hoy.year)
    estado = request.GET.get('estado', '')
    buscar = request.GET.get('buscar', '')

    # Detectar período para el reporte
    periodo = "Todos"
    if mes and año:
        periodo = f"{MESES_ES[int(mes)]} {año}"
    elif año:
        periodo = f"Año {año}"

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
            Q(nombre_cliente__icontains=buscar) | Q(concepto__icontains=buscar) | Q(detalle__icontains=buscar)
        )

    cobros = cobros.select_related('cliente').order_by('fecha_vencimiento')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cobros"

    from openpyxl.styles import Font, PatternFill, Alignment
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="3b82f6", end_color="3b82f6", fill_type="solid")

    # ENCABEZADO DEL EXCEL CON PERÍODO
    ws.append(['LISTADO DE COBROS'])
    ws.append(['Período:', periodo])
    ws.append(['Fecha de Emisión:', hoy.strftime('%d/%m/%Y')])
    ws.append([])

    # TABLA
    ws.append(['Cliente', 'Concepto', 'Detalle', 'Total', 'Pagado', 'Saldo', 'Vencimiento', 'Estado'])
    header_row = ws.max_row
    for cell in ws[header_row]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    total_facturado = total_cobrado = total_pendiente = 0
    for c in cobros:
        fecha = c.fecha_vencimiento.strftime('%d/%m/%Y') if c.fecha_vencimiento else c.fecha_emision.strftime('%d/%m/%Y')
        est = 'Programado' if c.estado in ['pendiente', 'parcial'] and c.fecha_vencimiento and c.fecha_vencimiento > hoy else c.get_estado_display()

        ws.append([c.nombre_cliente, c.concepto, c.detalle, float(c.monto_total), float(c.monto_pagado), float(c.saldo), fecha, est])
        total_facturado += float(c.monto_total)
        total_cobrado += float(c.monto_pagado)
        total_pendiente += float(c.saldo)

    ws.append([])
    ws.append(['', '', 'TOTALES:', total_facturado, total_cobrado, total_pendiente, '', ''])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)

    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 25

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Cobros_{periodo.replace(" ", "_")}.xlsx"'
    return response


@login_required
def exportar_cobros_pdf(request):
    hoy = hoy_local()
    mes = request.GET.get('mes', hoy.month)
    año = request.GET.get('año', hoy.year)
    estado = request.GET.get('estado', '')
    buscar = request.GET.get('buscar', '')

    periodo = "Todos"
    if mes and año:
        periodo = f"{MESES_ES[int(mes)]} {año}"
    elif año:
        periodo = f"Año {año}"

    cobros = Cobro.objects.filter(usuario=request.user)
    if mes:
        mes = int(mes)
        if año:
            año = int(año)
            cobros = cobros.filter(fecha_vencimiento__month=mes, fecha_vencimiento__year=año)
    elif año:
        año = int(año)
        cobros = cobros.filter(fecha_vencimiento__year=año)

    if estado: cobros = cobros.filter(estado=estado)
    if buscar:
        cobros = cobros.filter(Q(nombre_cliente__icontains=buscar) | Q(concepto__icontains=buscar) | Q(detalle__icontains=buscar))

    cobros = cobros.select_related('cliente').order_by('fecha_vencimiento')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Cobros_{periodo.replace(" ", "_")}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=20*mm)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("LISTADO DE COBROS", styles['Title']))
    elements.append(Paragraph(f"<b>Período:</b> {periodo}", styles['Normal']))
    elements.append(Paragraph(f"<b>Fecha de emisión del reporte:</b> {hoy.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 15))

    data = [['Cliente', 'Concepto', 'Total', 'Pagado', 'Saldo', 'Vence', 'Estado']]
    total_facturado = total_cobrado = total_pendiente = 0

    for c in cobros:
        fecha = c.fecha_vencimiento.strftime('%d/%m/%Y') if c.fecha_vencimiento else c.fecha_emision.strftime('%d/%m/%Y')
        est = 'Programado' if c.estado in ['pendiente', 'parcial'] and c.fecha_vencimiento and c.fecha_vencimiento > hoy else c.get_estado_display()

        data.append([Paragraph(c.nombre_cliente, styles['Normal']), Paragraph(c.concepto or '-', styles['Normal']), f'${c.monto_total:,.2f}', f'${c.monto_pagado:,.2f}', f'${c.saldo:,.2f}', fecha, est])
        total_facturado += float(c.monto_total)
        total_cobrado += float(c.monto_pagado)
        total_pendiente += float(c.saldo)

    data.append(['', 'TOTALES:', f'${total_facturado:,.2f}', f'${total_cobrado:,.2f}', f'${total_pendiente:,.2f}', '', ''])

    t = Table(data, colWidths=[100, 100, 65, 65, 65, 55, 55])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 0), (4, -1), 'RIGHT'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8f9fa')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    doc.build(elements)
    return response


@login_required
def exportar_gastos_excel(request):
    hoy = hoy_local()
    mes = request.GET.get('mes', hoy.month)
    año = request.GET.get('año', hoy.year)
    estado = request.GET.get('estado', '')
    buscar = request.GET.get('buscar', '')

    periodo = "Todos"
    if mes and año:
        periodo = f"{MESES_ES[int(mes)]} {año}"
    elif año:
        periodo = f"Año {año}"

    gastos = Gasto.objects.filter(usuario=request.user)
    if mes:
        mes = int(mes)
        if año:
            año = int(año)
            gastos = gastos.filter(Q(fecha_vencimiento__month=mes, fecha_vencimiento__year=año) | Q(fecha_vencimiento__isnull=True, fecha__month=mes, fecha__year=año))
    elif año:
        año = int(año)
        gastos = gastos.filter(Q(fecha_vencimiento__year=año) | Q(fecha_vencimiento__isnull=True, fecha__year=año))

    if estado: gastos = gastos.filter(estado=estado)
    if buscar: gastos = gastos.filter(Q(nombre__icontains=buscar) | Q(categoria__nombre__icontains=buscar))

    gastos = gastos.select_related('categoria').order_by('fecha_vencimiento', 'fecha')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Gastos"

    from openpyxl.styles import Font, PatternFill
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="ef4444", end_color="ef4444", fill_type="solid")

    ws.append(['LISTADO DE GASTOS'])
    ws.append(['Período:', periodo])
    ws.append(['Fecha de Emisión:', hoy.strftime('%d/%m/%Y')])
    ws.append([])

    ws.append(['Vencimiento', 'Concepto', 'Categoría', 'Monto', 'Forma de Pago', 'Estado'])
    header_row = ws.max_row
    for cell in ws[header_row]:
        cell.font = header_font
        cell.fill = header_fill

    total_gastos = 0
    for g in gastos:
        fecha = g.fecha_vencimiento.strftime('%d/%m/%Y') if g.fecha_vencimiento else g.fecha.strftime('%d/%m/%Y')
        monto = float(g.monto) if g.monto else 0
        total_gastos += monto
        ws.append([fecha, g.nombre, g.categoria.nombre, monto, g.get_forma_pago_display(), g.get_estado_display()])

    ws.append([])
    ws.append(['', '', 'TOTAL:', total_gastos, '', ''])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)

    ws.column_dimensions['B'].width = 30

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Gastos_{periodo.replace(" ", "_")}.xlsx"'
    return response


@login_required
def exportar_gastos_pdf(request):
    hoy = hoy_local()
    mes = request.GET.get('mes', hoy.month)
    año = request.GET.get('año', hoy.year)
    estado = request.GET.get('estado', '')
    buscar = request.GET.get('buscar', '')

    periodo = "Todos"
    if mes and año:
        periodo = f"{MESES_ES[int(mes)]} {año}"
    elif año:
        periodo = f"Año {año}"

    gastos = Gasto.objects.filter(usuario=request.user)
    if mes:
        mes = int(mes)
        if año:
            año = int(año)
            gastos = gastos.filter(Q(fecha_vencimiento__month=mes, fecha_vencimiento__year=año) | Q(fecha_vencimiento__isnull=True, fecha__month=mes, fecha__year=año))
    elif año:
        año = int(año)
        gastos = gastos.filter(Q(fecha_vencimiento__year=año) | Q(fecha_vencimiento__isnull=True, fecha__year=año))

    if estado: gastos = gastos.filter(estado=estado)
    if buscar: gastos = gastos.filter(Q(nombre__icontains=buscar) | Q(categoria__nombre__icontains=buscar))

    gastos = gastos.select_related('categoria').order_by('fecha_vencimiento', 'fecha')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Gastos_{periodo.replace(" ", "_")}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=20*mm)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("LISTADO DE GASTOS", styles['Title']))
    elements.append(Paragraph(f"<b>Período:</b> {periodo}", styles['Normal']))
    elements.append(Paragraph(f"<b>Fecha de emisión del reporte:</b> {hoy.strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 15))

    data = [['Fecha', 'Concepto', 'Categoría', 'Monto', 'Pago', 'Estado']]
    total_gastos = 0

    for g in gastos:
        fecha = g.fecha_vencimiento.strftime('%d/%m/%Y') if g.fecha_vencimiento else g.fecha.strftime('%d/%m/%Y')
        monto = float(g.monto) if g.monto else 0
        total_gastos += monto

        data.append([fecha, Paragraph(g.nombre, styles['Normal']), Paragraph(g.categoria.nombre, styles['Normal']), f'${monto:,.2f}', g.get_forma_pago_display(), g.get_estado_display()])

    data.append(['', '', 'TOTAL:', f'${total_gastos:,.2f}', '', ''])

    t = Table(data, colWidths=[65, 150, 90, 70, 70, 60])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f8f9fa')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    elements.append(t)
    doc.build(elements)
    return response


@login_required
def vencidos_impagos(request):
    actualizar_estados(request)
    
    cobros_vencidos = Cobro.objects.filter(
        usuario=request.user, estado='vencido'
    ).select_related('cliente').order_by('fecha_vencimiento')
    
    gastos_vencidos = Gasto.objects.filter(
        usuario=request.user, estado='vencido'
    ).select_related('categoria').order_by('fecha_vencimiento')
    
    total_cobros = cobros_vencidos.aggregate(total=Sum('saldo'))['total'] or 0
    total_gastos = gastos_vencidos.aggregate(total=Sum('monto'))['total'] or 0
    
    return render(request, 'finances/vencidos.html', {
        'cobros_vencidos': cobros_vencidos,
        'gastos_vencidos': gastos_vencidos,
        'total_cobros': total_cobros,
        'total_gastos': total_gastos,
    })


# ============ CALENDARIO ============

@login_required
def vista_calendario(request):
    return render(request, 'finances/calendario.html')


@login_required
def api_eventos_calendario(request):
    """Devuelve un JSON con los cobros y gastos para el calendario"""
    eventos = []
    
    # Traemos Cobros y Gastos del usuario
    cobros = Cobro.objects.filter(usuario=request.user)
    gastos = Gasto.objects.filter(usuario=request.user)

    for c in cobros:
        if c.fecha_vencimiento:
            eventos.append({
                'title': f"Cobro: {c.nombre_cliente}",
                'start': c.fecha_vencimiento.strftime('%Y-%m-%d'),
                'color': '#10b981', # Verde para cobros
                'extendedProps': {
                    'tipo': 'cobro',
                    'estado': c.get_estado_display(),
                    'monto': f"${c.monto_total:,.2f}",
                    'fecha': c.fecha_vencimiento.strftime('%d/%m/%Y'),
                    'detalle': c.concepto or c.detalle or 'Sin detalle',
                    'link': f"/cobros/editar/{c.id}/"
                }
            })

    for g in gastos:
        fecha = g.fecha_vencimiento or g.fecha
        if fecha:
            eventos.append({
                'title': f"Gasto: {g.nombre}",
                'start': fecha.strftime('%Y-%m-%d'),
                'color': '#ef4444', # Rojo para gastos
                'extendedProps': {
                    'tipo': 'gasto',
                    'estado': g.get_estado_display(),
                    'monto': f"${g.monto:,.2f}" if g.monto else "Sin monto",
                    'fecha': fecha.strftime('%d/%m/%Y'),
                    'detalle': g.categoria.nombre,
                    'link': f"/gastos/editar/{g.id}/"
                }
            })

    return JsonResponse(eventos, safe=False)