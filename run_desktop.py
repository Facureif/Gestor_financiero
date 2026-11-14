import os
import sys
import subprocess
import threading
import time
import socket
import signal

# ===== CONFIGURACIÓN =====
PORT = 8000

def is_port_open(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def kill_process_on_port(port):
    try:
        result = subprocess.run(f'netstat -ano | findstr :{port}', 
                               shell=True, capture_output=True, text=True)
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
        time.sleep(1)
    except:
        pass

def get_base_dir():
    """Obtiene el directorio base (donde está el .exe o el script)"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))

def start_django():
    """Inicia el servidor Django"""
    base_dir = get_base_dir()
    
    # Agregar al path
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    
    # Cambiar al directorio del proyecto
    os.chdir(base_dir)
    
    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    os.environ['DESKTOP_MODE'] = 'true'
    
    # Iniciar servidor
    cmd = [sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{PORT}', '--noreload']
    
    try:
        subprocess.run(cmd, capture_output=False)
    except Exception as e:
        print(f"Error iniciando servidor: {e}")
        # Intentar sin --noreload
        cmd = [sys.executable, 'manage.py', 'runserver', f'127.0.0.1:{PORT}']
        subprocess.run(cmd, capture_output=False)

def main():
    print("=" * 50)
    print("  💰 Gestor Financiero v1.0")
    print("=" * 50)
    print(f"  Iniciando servidor en http://127.0.0.1:{PORT}")
    print("  Espera unos segundos...")
    print("=" * 50)
    
    # Matar proceso anterior
    kill_process_on_port(PORT)
    
    # Iniciar Django en un hilo
    server_thread = threading.Thread(target=start_django, daemon=True)
    server_thread.start()
    
    # Esperar a que esté listo
    max_wait = 30
    waited = 0
    while not is_port_open(PORT) and waited < max_wait:
        time.sleep(1)
        waited += 1
        print(f"  ⏳ Esperando servidor... ({waited}s)")
    
    if not is_port_open(PORT):
        print("  ❌ No se pudo iniciar el servidor")
        input("  Presiona Enter para salir...")
        return
    
    print(f"  ✅ Servidor iniciado!")
    print(f"  🌐 Abriendo: http://127.0.0.1:{PORT}")
    print("=" * 50)
    print("  No cierres esta ventana mientras usas la app")
    print("=" * 50)
    
    # Abrir en navegador
    import webbrowser
    webbrowser.open(f'http://127.0.0.1:{PORT}')
    
    # Mantener vivo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  👋 Cerrando servidor...")
        kill_process_on_port(PORT)

if __name__ == '__main__':
    main()