@echo off
call venv\Scripts\activate.bat
cd backend
echo  Starting Voyaga at http://127.0.0.1:8000
echo  Press Ctrl+C to stop
echo.
python manage.py runserver
