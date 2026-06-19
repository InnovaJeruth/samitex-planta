@echo off
REM ── Setup del entorno virtual para Samitex Planta ──────────
REM Ejecutar una sola vez al clonar el proyecto

echo Creando entorno virtual...
python -m venv .venv

echo Activando entorno...
call .venv\Scripts\activate.bat

echo Instalando dependencias de produccion...
pip install -r requirements.txt

echo Instalando dependencias de desarrollo...
pip install -r requirements-dev.txt

echo Copiando archivo de configuracion...
if not exist .env (
    copy .env.example .env
    echo IMPORTANTE: Edita el archivo .env con tus credenciales de BD y claves secretas.
)

echo.
echo Setup completado. Para iniciar el servidor:
echo   .venv\Scripts\activate
echo   uvicorn app.main:app --reload
echo.
pause
