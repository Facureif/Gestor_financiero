# Gestor Financiero

Sistema integral de gestión financiera y cobranzas desarrollado con Django. Permite administrar cobros recurrentes, gastos, clientes y generar reportes detallados.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Django](https://img.shields.io/badge/Django-6.0-green?logo=django)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.1-purple?logo=bootstrap)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Características

### 📊 Dashboard
- Métricas del mes (cobrado, pendiente, gastos, balance)
- Gráfico de gastos por categoría (Chart.js)
- Efectividad de cobranza con barra de progreso
- Alertas de vencimientos próximos y vencidos

### 💵 Cobranzas
- CRUD completo de cobros con clientes
- Generación automática de cobros recurrentes (3, 6, 12 meses)
- Registro de pagos parciales con cálculo automático de saldos
- Actualización masiva de precios a cobros siguientes
- Comprobante PDF descargable para el cliente
- Subida de comprobantes de pago

### 🛒 Gastos
- Registro de gastos fijos y variables
- Gastos recurrentes con generación automática mensual
- Pagos automáticos (débito) sin monto obligatorio
- Categorías personalizables por usuario
- Subida de facturas/comprobantes

### 👥 Clientes
- Ficha técnica con datos de contacto, sistema y plan
- Modal de creación rápida desde el formulario de cobro
- Historial de cobros por cliente con ficha integrada

### 📈 Reportes
- Resumen mensual de cobros con efectividad
- Resumen anual de cobros por mes
- Resumen general (cobros vs gastos) mensual y anual
- Exportación a Excel
- Filtros por mes, año, estado y búsqueda por texto

### 🔔 Notificaciones
- Alertas automáticas de cobros vencidos
- Notificaciones de próximos vencimientos (3 días)
- Panel de notificaciones con marcado de leídas

### 👤 Usuarios
- Sistema de login y registro
- Datos separados por usuario
- Categorías predefinidas al registrarse

## 🚀 Tecnologías

| Tecnología | Uso |
|------------|-----|
| **Python 3.10+** | Backend |
| **Django 6.0** | Framework web |
| **SQLite** | Base de datos (desarrollo) |
| **Bootstrap 5** | Interfaz responsive |
| **Chart.js** | Gráficos dinámicos |
| **ReportLab** | Generación de PDF |
| **OpenPyXL** | Exportación Excel |

## 📸 Capturas de Pantalla

*(Agregá tus capturas aquí)*

## 🔧 Instalación Local

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/gestor-financiero.git
cd gestor-financiero

# 2. Crear entorno virtual
python -m venv venv

# 3. Activar entorno
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Migrar base de datos
python manage.py makemigrations finances
python manage.py migrate

# 6. Crear superusuario
python manage.py createsuperuser

# 7. Iniciar servidor
python manage.py runserver
