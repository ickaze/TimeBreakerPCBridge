@echo off
setlocal
cd /d "%~dp0"
if defined TIMEBREAKER_PYTHON (
  "%TIMEBREAKER_PYTHON%" -c "import sys; assert sys.version_info[:3] == (3,13,16) and sys.maxsize > 2**32, 'Use Windows x64 Python 3.13.16'"
) else (
  py -3.13 -c "import sys; assert sys.version_info[:3] == (3,13,16) and sys.maxsize > 2**32, 'Use Windows x64 Python 3.13.16'"
)
if errorlevel 1 goto failed
if defined TIMEBREAKER_PYTHON (
  "%TIMEBREAKER_PYTHON%" -m venv --clear .build_venv
) else (
  py -3.13 -m venv --clear .build_venv
)
if errorlevel 1 goto failed
.build_venv\Scripts\python.exe -m pip install --only-binary=:all: --require-hashes -r requirements-build.lock -r requirements-runtime.lock
if errorlevel 1 goto failed
.build_venv\Scripts\python.exe tools\build_release.py
if errorlevel 1 goto failed
echo Build complete. See release\ and BUILD_MANIFEST.json in the release ZIP.
if not "%CI%"=="true" pause
exit /b 0
:failed
echo Build FAILED. No new release should be published. Save this console output.
if not "%CI%"=="true" pause
exit /b 1
