@echo off
title Instalador - Monitor de Sitios Web Pro
setlocal

echo ====================================================
echo   Instalador de Dependencias - Monitor Web Pro
echo ====================================================
echo.

:: Verificar si Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Por favor, instala Python 3.14 o superior desde python.org
    pause
    exit /b
)

echo [1/3] Actualizando pip...
python -m pip install --upgrade pip --quiet

echo [2/3] Instalando dependencias desde requirements.txt...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Hubo un problema al instalar las dependencias.
    pause
    exit /b
)

echo [3/3] Verificando carpetas...
if not exist "alarmas" (
    mkdir "alarmas"
    echo Carpeta 'alarmas' creada.
)

echo.
echo ====================================================
echo   INSTALACION COMPLETADA CON EXITO
echo ====================================================
echo.
echo Puedes usar 'iniciar_monitor.bat' para abrir la app.
echo.
pause
exit