@echo off
rem Windows runner, no WSL: randomize.bat [options], the same options as randomize.sh.
rem The virtual environment %USERPROFILE%\.venvs\er_mod is built on first use from a Python 3.10-3.14
rem (the dependencies have no wheels for 3.15 yet) and reused afterwards; a missing package is reinstalled.
rem All messages are ASCII on purpose: cmd shows UTF-8 text as garbage in the default code page.
setlocal
cd /d "%~dp0"
set "VENV=%USERPROFILE%\.venvs\er_mod"
set "PY="
for /f "delims=" %%P in ('tools\findpython.bat') do set "PY=%%P"
if not defined PY (
  echo No Python 3.10 to 3.14 found. Install Python 3.14 from python.org, ticking the tcl/tk and IDLE box, and run again.
  goto :fail
)
if not exist "%VENV%\Scripts\python.exe" %PY% -m venv "%VENV%" || goto :fail
"%VENV%\Scripts\python.exe" -c "import zstandard, cryptography" >nul 2>&1 || (
  echo Installing the dependencies into %VENV% ...
  "%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r tools\requirements.txt || goto :fail
)
set PYTHONDONTWRITEBYTECODE=1
"%VENV%\Scripts\python.exe" -I tools\randomize.py %*
exit /b %errorlevel%

:fail
echo.
echo Failed, see the messages above.
pause
exit /b 1