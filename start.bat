@echo off
REM ============================================
REM IsoSmart Titanium - Inicio Rápido (Windows)
REM ============================================

echo ============================================
echo   IsoSmart Titanium v4.0
echo   Iniciando aplicacion...
echo ============================================
echo.

REM Verificar si existe el entorno virtual
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Creando entorno virtual...
    python -m venv venv
    echo [INFO] Instalando dependencias...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    echo.
    echo [INFO] Instalacion completada!
    echo.
)

REM Activar entorno virtual
call venv\Scripts\activate.bat

REM Ejecutar Streamlit
echo [INFO] Iniciando servidor...
echo.
streamlit run app.py

pause
