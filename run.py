import os
import sys
import subprocess
import webbrowser
import threading
import time
import socket

def is_port_open(port):
    """Verifica si el puerto ya está en uso"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def start_server():
    """Inicia el servidor Django"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    
    import django
    django.setup()
    from django.core.management import call_command
    
    # Migrar si es necesario
    try:
        call_command('migrate', '--run-syncdb', verbosity=0)
    except:
        pass
    
    # Iniciar servidor
    subprocess.run([sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000', '--noreload'])

if __name__ == '__main__':
    print("💰 Iniciando Gestor Financiero...")
    
    if is_port_open(8000):
        print("✅ El servidor ya está corriendo. Abriendo navegador...")
        webbrowser.open('http://127.0.0.1:8000')
    else:
        # Iniciar servidor en un hilo
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        
        # Esperar a que el servidor esté listo
        print("⏳ Iniciando servidor...")
        while not is_port_open(8000):
            time.sleep(0.5)
        
        print("✅ Servidor iniciado. Abriendo navegador...")
        webbrowser.open('http://127.0.0.1:8000')
    
    print("=" * 50)
    print("  💰 Gestor Financiero - App de Escritorio")
    print("  Abrí: http://127.0.0.1:8000")
    print("  Cerrá esta ventana para salir")
    print("=" * 50)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 ¡Hasta luego!")