@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the project environment...
    py -3.12 -m venv .venv
    if errorlevel 1 goto python_error
)

echo Checking and installing project dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto dependency_error

pushd backend
echo Preparing the database...
"..\.venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto setup_error

echo Preparing demo accounts and sample data...
"..\.venv\Scripts\python.exe" manage.py seed_m1_demo_accounts
if errorlevel 1 goto setup_error
"..\.venv\Scripts\python.exe" manage.py seed_demo_catalog
if errorlevel 1 goto setup_error
"..\.venv\Scripts\python.exe" manage.py seed_demo_sales
if errorlevel 1 goto setup_error

echo.
echo Quy Thu is ready at http://127.0.0.1:8000/
echo Login password for all demo accounts: Quythu123!
echo Press Ctrl+C to stop the server.
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000/"
"..\.venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%

:python_error
echo.
echo Python 3.12 is required. Install Python 3.12 and make sure the Windows Python Launcher (py) is available.
pause
exit /b 1

:dependency_error
echo.
echo Could not install dependencies. Check your internet connection and run this file again.
pause
exit /b 1

:setup_error
echo.
echo Database or demo data setup failed. Read the error above, then run this file again.
popd
pause
exit /b 1
