@echo off
setlocal
cd /d "%~dp0"
if defined TIMEBREAKER_PYTHON goto specified
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) and sys.maxsize > 2**32 else 1)" >nul 2>&1
if not errorlevel 1 goto launcher
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) and sys.maxsize > 2**32 else 1)" >nul 2>&1
if not errorlevel 1 goto pathpython
goto missing
:specified
"%TIMEBREAKER_PYTHON%" tools\setup_source.py
if errorlevel 1 goto failed
goto success
:launcher
py -3 tools\setup_source.py
if errorlevel 1 goto failed
goto success
:pathpython
python tools\setup_source.py
if errorlevel 1 goto failed
goto success
:missing
echo No compatible Python found. Source setup needs 64-bit Python 3.11 or later.
echo Run: py --list
echo Install official Windows x64 Python from https://www.python.org/downloads/windows/
echo Or set TIMEBREAKER_PYTHON to the full path of your existing python.exe.
echo Release builds still require Python 3.13.16.
echo No driver changes were made.
pause
exit /b 1
:success
echo Source environment ready. Run start_windows.bat.
echo Drivers are managed separately in the GUI. Log: setup_windows.log
pause
exit /b 0
:failed
echo Setup FAILED. See setup_windows.log if created, and save this console output.
pause
exit /b 1
