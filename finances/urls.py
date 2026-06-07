from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    # Cobros
    path('cobros/', views.lista_cobros, name='lista_cobros'),
    path('cobros/crear/', views.crear_cobro, name='crear_cobro'),
    path('cobros/editar/<int:pk>/', views.editar_cobro, name='editar_cobro'),
    path('cobros/pagar/<int:pk>/', views.registrar_pago, name='registrar_pago'),
    path('cobros/historial/<str:nombre>/', views.historial_cliente, name='historial_cliente'),
    path('cobros/generar-siguiente/<int:pk>/', views.generar_cobro_siguiente, name='generar_cobro_siguiente'),
    path('cobros/eliminar/<int:pk>/', views.eliminar_cobro, name='eliminar_cobro'),
    path('cobros/resumen/', views.resumen_cobros_mensual, name='resumen_mensual'),
    path('cobros/resumen/<int:año>/<int:mes>/', views.resumen_cobros_mensual, name='resumen_mensual_fecha'),
    path('cobros/ajustar/<int:pk>/', views.ajustar_precio_desde, name='ajustar_precio'),
    path('cobros/resumen-anual/', views.resumen_cobros_anual, name='resumen_anual'),
    path('cobros/resumen-anual/<int:año>/', views.resumen_cobros_anual, name='resumen_anual_fecha'),

    # Clientes
    path('clientes/crear-ajax/', views.crear_cliente_ajax, name='crear_cliente_ajax'),
    path('clientes/editar/<int:pk>/', views.editar_cliente, name='editar_cliente'),



    # Gastos
    path('gastos/', views.lista_gastos, name='lista_gastos'),
    path('gastos/crear/', views.crear_gasto, name='crear_gasto'),
    path('gastos/pagar/<int:pk>/', views.pagar_gasto, name='pagar_gasto'),
    path('gastos/editar/<int:pk>/', views.editar_gasto, name='editar_gasto'),
    path('gastos/editar/<int:pk>/', views.editar_gasto, name='editar_gasto'),
    path('gastos/generar-siguiente/<int:pk>/', views.generar_gasto_siguiente, name='generar_gasto_siguiente'),
    path('gastos/eliminar/<int:pk>/', views.eliminar_gasto, name='eliminar_gasto'),
    path('gastos/resumen/', views.resumen_gastos_mensual, name='resumen_gastos_mensual'),
    path('gastos/resumen/<int:año>/<int:mes>/', views.resumen_gastos_mensual, name='resumen_gastos_mensual_fecha'),
    path('gastos/resumen-anual/', views.resumen_gastos_anual, name='resumen_gastos_anual'),
    path('gastos/resumen-anual/<int:año>/', views.resumen_gastos_anual, name='resumen_gastos_anual_fecha'),

    # Resumen general
    path('resumen/', views.resumen_general_mensual, name='resumen_general'),
    path('resumen/<int:año>/<int:mes>/', views.resumen_general_mensual, name='resumen_general_fecha'),
    path('resumen-anual/', views.resumen_general_anual, name='resumen_general_anual'),
    path('resumen-anual/<int:año>/', views.resumen_general_anual, name='resumen_general_anual_fecha'),

    # Otros
    path('exportar/excel/', views.exportar_excel, name='exportar_excel'),
    path('notificaciones/', views.notificaciones_lista, name='notificaciones'),
    path('notificaciones/leer/<int:pk>/', views.marcar_notificacion_leida, name='marcar_leida'),
    path('notificaciones/leer-todas/', views.marcar_todas_leidas, name='marcar_todas_leidas'),
    path('cobros/comprobante-pdf/<int:pk>/', views.generar_comprobante_pdf, name='comprobante_pdf'),
]