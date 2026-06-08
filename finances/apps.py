from django.apps import AppConfig


class FinancesConfig(AppConfig):
    name = 'finances'


from django.apps import AppConfig

class FinancesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finances'
    
    def ready(self):
        # Crear datos demo automáticamente en Render
        import os
        if os.environ.get('RENDER'):
            from django.db.models.signals import post_migrate
            from .signals import crear_datos_demo
            post_migrate.connect(crear_datos_demo, sender=self) 