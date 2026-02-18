@echo off
echo.
echo  ============================================
echo   VOYAGA - Setup Script
echo  ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Download from https://python.org
    pause & exit /b 1
)

echo [1/6] Creating virtual environment...
python -m venv venv
if errorlevel 1 ( echo [ERROR] Failed to create venv & pause & exit /b 1 )

echo [2/6] Installing packages...
call venv\Scripts\activate.bat
pip install Django==4.2.9 djangorestframework==3.14.0 djangorestframework-simplejwt==5.3.1 Pillow==10.2.0 django-cors-headers==4.3.1 python-dotenv==1.0.0 openai==1.12.0 -q
if errorlevel 1 ( echo [ERROR] pip install failed & pause & exit /b 1 )

echo [3/6] Running database migrations...
cd backend
python manage.py migrate
if errorlevel 1 ( echo [ERROR] migrate failed & pause & exit /b 1 )

echo [4/6] Creating admin account...
python manage.py shell -c "from apps.core.models import User; User.objects.filter(email='admin@voyaga.com').exists() or User.objects.create_superuser('admin','admin@voyaga.com','admin123',role='admin',first_name='Admin')"

echo [5/6] Loading sample properties...
cd ..
python seed_data.py

echo [6/6] Done!
echo.
echo  ============================================
echo   Setup complete! 
echo  ============================================
echo.
echo   Login accounts:
echo     Admin:  admin@voyaga.com  / admin123
echo     Host:   host@voyaga.com   / host123
echo     Guest:  guest@voyaga.com  / guest123
echo.
echo   To START the server, run:  run.bat
echo   Then open:  http://127.0.0.1:8000
echo.
pause
