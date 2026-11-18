@echo off
rem Windows GUI from source (no packing, no WSL): randomize_gui.bat
rem The virtual environment %USERPROFILE%\.venvs\er_mod is built on first use from a Python 3.10-3.14
rem (the dependencies have no wheels for 3.15 yet) and reused afterwards.
rem This black window stays open to show error messages; closing it closes the GUI too. For a program without
rem the console window use the exe built by build_exe.bat.
rem Every failure stops with a pause so the error can be read.
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
"%VENV%\Scripts\python.exe" -c "import tkinter" >nul 2>&1 || (
  echo This Python has no tkinter, so the window cannot be drawn.
  echo Install Python from python.org with "tcl/tk and IDLE" ticked, delete %VENV% and run this again.
  goto :fail
)
set PYTHONDONTWRITEBYTECODE=1
"%VENV%\Scripts\python.exe" -I tools\gui.py
if errorlevel 1 (
  echo.
  echo The GUI did not exit normally; see the messages above.
  pause
)
exit /b 0

:fail
echo.
echo Failed, see the messages above.
pause
exit /b 1