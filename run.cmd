@echo off
setlocal
where py >nul 2>&1
if not errorlevel 1 goto use_py
where python >nul 2>&1
if not errorlevel 1 goto use_python
set "INVENTORY_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%INVENTORY_PYTHON%" goto use_bundled
echo Python 3.8 or later is required. Install Python, then run this file again. 1>&2
exit /b 1

:use_py
py -3 "%~dp0main.py" %*
exit /b %errorlevel%

:use_python
python "%~dp0main.py" %*
exit /b %errorlevel%

:use_bundled
"%INVENTORY_PYTHON%" "%~dp0main.py" %*
exit /b %errorlevel%
