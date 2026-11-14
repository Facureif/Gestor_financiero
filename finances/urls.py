from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    # Cobros
    path('cobros/', views.lista_cobros, name='lista_cobros'),
    path('cobros/crear/', views.crear_cobro, name='crear_cobro'),
    path('cobros/editar/<int:pk>/', views.editar_cobro, name='editar_cobro'),
    path('cobros/pagar/<int:pk>/', views.registrar_pago, name='registrar_pago'),
    path('cobros/historial/<slug:slug>/', views.historial_cliente, name='historial_cliente'),
    path('cobros/generar-siguiente/<int:pk>/', views.generar_cobro_siguiente, name='generar_cobro_siguiente'),
    path('cobros/eliminar/<int:pk>/', views.eliminar_cobro, name='eliminar_cobro'),
    path('cobros/resumen/', views.resumen_cobros_mensual, name='resumen_mensual'),
    path('cobros/resumen/<int:año>/<int:mes>/', views.resumen_cobros_mensual, name='resumen_mensual_fecha'),
    path('cobros/ajustar/<int:pk>/', views.ajustar_precio_desde, name='ajustar_precio'),
    path('cobros/cancelar-futuros/<int:pk>/', views.cancelar_cobros_futuros, name='cancelar_cobros_futuros'),

    # Clientes
    path('clientes/', views.lista_clientes, name='lista_clientes'),         
    path('clientes/crear/', views.crear_cliente, name='crear_cliente'),    
    path('clientes/crear-ajax/', views.crear_cliente_ajax, name='crear_cliente_ajax'),
    path('clientes/editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),
    path('clientes/historial/<slug:slug>/', views.historial_cliente, name='historial_cliente'),
    path('clientes/historial/<slug:slug>/excel/', views.exportar_historial_excel, name='exportar_historial_excel'),
    path('clientes/historial/<slug:slug>/pdf/', views.exportar_historial_pdf, name='exportar_historial_pdf'),


    # Gastos
    path('gastos/', views.lista_gastos, name='lista_gastos'),
    path('gastos/crear/', views.crear_gasto, name='crear_gasto'),
    path('gastos/pagar/<int:pk>/', views.pagar_gasto, name='pagar_gasto'),
    path('gastos/editar/<int:pk>/', views.editar_gasto, name='editar_gasto'),
    path('gastos/generar-siguiente/<int:pk>/', views.generar_gasto_siguiente, name='generar_gasto_siguiente'),
    path('gastos/eliminar/<int:pk>/', views.eliminar_gasto, name='eliminar_gasto'),
    path('gastos/resumen/', views.resumen_gastos_mensual, name='resumen_gastos_mensual'),
    path('gastos/resumen/<int:año>/<int:mes>/', views.resumen_gastos_mensual, name='resumen_gastos_mensual_fecha'),
    path('gastos/resumen-anual/', views.resumen_gastos_anual, name='resumen_gastos_anual'),
    path('gastos/resumen-anual/<int:año>/', views.resumen_gastos_anual, name='resumen_gastos_anual_fecha'),

    # Resumen general
    path('resumen-anual/', views.resumen_general_anual, name='resumen_general_anual'),
    path('resumen-anual/<int:año>/', views.resumen_general_anual, name='resumen_general_anual_fecha'),
    path('resumen/balance/<int:año>/<int:mes>/excel/', views.exportar_balance_excel, name='exportar_balance_excel'),
    path('resumen/balance/<int:año>/<int:mes>/pdf/', views.exportar_balance_pdf, name='exportar_balance_pdf'),

    # Otros
    path('notificaciones/', views.notificaciones_lista, name='notificaciones'),
    path('notificaciones/leer/<int:pk>/', views.marcar_notificacion_leida, name='marcar_leida'),
    path('notificaciones/leer-todas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),
    path('cobros/comprobante-pdf/<int:pk>/', views.generar_comprobante_pdf, name='comprobante_pdf'),
    path('categorias/crear-ajax/', views.crear_categoria_ajax, name='crear_categoria_ajax'),
    path('cobros/exportar/excel/', views.exportar_cobros_excel, name='exportar_cobros_excel'),
    path('cobros/exportar/pdf/', views.exportar_cobros_pdf, name='exportar_cobros_pdf'),
    path('gastos/exportar/excel/', views.exportar_gastos_excel, name='exportar_gastos_excel'),
    path('gastos/exportar/pdf/', views.exportar_gastos_pdf, name='exportar_gastos_pdf'),
    path('vencidos/', views.vencidos_impagos, name='vencidos_impagos'),

    # Calendario
    path('calendario/', views.vista_calendario, name='calendario'),
    path('api/calendario/', views.api_eventos_calendario, name='api_eventos_calendario'),

]