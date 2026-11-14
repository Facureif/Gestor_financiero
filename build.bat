@echo off
echo 📦 Compilando Gestor Financiero...

pyinstaller ^
    --name="GestorFinanciero" ^
    --onefile ^
    --console ^
    --add-data "finances;finances" ^
    --add-data "usuarios;usuarios" ^
    --add-data "config;config" ^
    --add-data "static;static" ^
    --add-data "manage.py;." ^
    --hidden-import django ^
    --hidden-import finances ^
    --hidden-import usuarios ^
    run_desktop.py

echo.
echo ✅ Listo: dist\GestorFinanciero.exe
pause