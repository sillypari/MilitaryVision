@echo off
setlocal
set "PROJECT_DIR=%~dp0.."
set "PYTHON_EXE=%PROJECT_DIR%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Virtual environment not found. Follow the installation steps in README.md.
    exit /b 1
)

set "PYTHONPYCACHEPREFIX=%PROJECT_DIR%\runtime\pycache"
pushd "%PROJECT_DIR%"
"%PYTHON_EXE%" -m pytest
set "TEST_EXIT=%ERRORLEVEL%"
popd
exit /b %TEST_EXIT%
