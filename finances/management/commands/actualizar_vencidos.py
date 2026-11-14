from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from finances.models import Cobro, Gasto, Notificacion


class Command(BaseCommand):
    help = 'Actualiza cobros y gastos vencidos, y genera notificaciones de próximos vencimientos'

    def handle(self, *args, **options):
        hoy = timezone.localtime(timezone.now()).date()
        total_cobros = 0
        total_gastos = 0
        total_notifs = 0

        # --- Cobros vencidos ---
        cobros_vencidos = Cobro.objects.filter(
            estado__in=['pendiente', 'parcial'],
            fecha_vencimiento__lt=hoy
        )
        for cobro in cobros_vencidos.select_related('usuario'):
            _, created = Notificacion.objects.get_or_create(
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
            if created:
                total_notifs += 1
        total_cobros = cobros_vencidos.update(estado='vencido')

        # --- Cobros próximos (3 días) ---
        fecha_limite = hoy + timedelta(days=3)
        cobros_proximos = Cobro.objects.filter(
            estado__in=['pendiente', 'parcial'],
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=fecha_limite
        )
        for cobro in cobros_proximos.select_related('usuario'):
            dias = (cobro.fecha_vencimiento - hoy).days
            _, created = Notificacion.objects.get_or_create(
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
            if created:
                total_notifs += 1

        # --- Gastos vencidos ---
        gastos_vencidos = Gasto.objects.filter(
            estado='pendiente',
            fecha_vencimiento__lt=hoy
        )
        for gasto in gastos_vencidos.select_related('usuario'):
            _, created = Notificacion.objects.get_or_create(
                gasto=gasto,
                tipo='gasto_vencido',
                defaults={
                    'titulo': f'⚠️ Gasto vencido: {gasto.nombre}',
                    'mensaje': (
                        f'El gasto "{gasto.nombre}"'
                        + (f' por ${gasto.monto:,.2f}' if gasto.monto else '')
                        + f' venció el {gasto.fecha_vencimiento.strftime("%d/%m/%Y")}.'
                    ),
                }
            )
            if created:
                total_notifs += 1
        total_gastos = gastos_vencidos.update(estado='vencido')

        # --- Gastos próximos (3 días) ---
        gastos_proximos = Gasto.objects.filter(
            estado='pendiente',
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=fecha_limite
        )
        for gasto in gastos_proximos.select_related('usuario'):
            dias = (gasto.fecha_vencimiento - hoy).days
            _, created = Notificacion.objects.get_or_create(
                gasto=gasto,
                tipo='recordatorio',
                fecha_creacion__date=hoy,
                defaults={
                    'titulo': f'📅 Gasto próximo: {gasto.nombre}',
                    'mensaje': (
                        f'El gasto "{gasto.nombre}"'
                        + (f' por ${gasto.monto:,.2f}' if gasto.monto else '')
                        + f' vence en {dias} día(s) '
                        f'({gasto.fecha_vencimiento.strftime("%d/%m/%Y")}).'
                    ),
                }
            )
            if created:
                total_notifs += 1

        self.stdout.write(self.style.SUCCESS(
            f'✅ {total_cobros} cobros vencidos · '
            f'{total_gastos} gastos vencidos · '
            f'{total_notifs} notificaciones creadas'
        ))