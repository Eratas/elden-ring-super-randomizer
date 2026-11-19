@echo off
rem Pack the window as a FOLDER build (dist\EldenRingSuperRandomizer\): the exe plus its DLLs and data next to it.
rem This is the antivirus-friendliest form: a --onedir exe does NOT unpack itself into %TEMP% at run time
rem (the classic dropper heuristic that gets --onefile PyInstaller builds flagged), so it is markedly less
rem likely to be a false positive than the single-file dist\EldenRingSuperRandomizer.exe.  The trade-off is that you
rem ship a folder, not one file.  See README "Antivirus notes" and build_exe.bat for the onefile build.
rem
rem tools\paramdef, tools\names and tools\msg land inside dist\EldenRingSuperRandomizer\ (PyInstaller --add-data), so
rem textarchives.MSG_DIR (next to the exe) finds msg\ there with nothing extra to copy.  The game's
rem oo2core_6_win64.dll is never shipped - it is RAD Game Tools' and comes with the game.
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
set "TCL_LIBRARY="
set "TK_LIBRARY="
for /f "tokens=1,* delims==" %%A in ('"%VENV%\Scripts\python.exe" -I tools\tkcheck.py') do set "%%A=%%B"
if not defined TCL_LIBRARY if not defined TK_LIBRARY (
  echo.
  echo This virtual environment's Python has no usable tkinter; the packed exe would have no window. Stopped.
  goto :fail
)
"%VENV%\Scripts\python.exe" -c "import PyInstaller" >nul 2>&1 || (
  echo Installing PyInstaller into %VENV% ...
  "%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check pyinstaller || goto :fail
)
rem --onedir (the default; --onefile is what build_exe.bat uses) keeps the runtime out of %TEMP%.
rem --version-file embeds PE version metadata; --hidden-import test_logic enables the exe's --self-test.
if not exist build mkdir build
set "LOG=%~dp0build\pyinstaller_dir.log"
echo Packing a folder build, this takes a minute or two; the full output is written to %LOG% ...
"%VENV%\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --noupx --name EldenRingSuperRandomizer ^
  --version-file "%~dp0tools\version_info.txt" ^
  --hidden-import test_logic ^
  --add-data "%~dp0tools\paramdef;paramdef" --add-data "%~dp0tools\names;names" --add-data "%~dp0tools\msg;msg" ^
  --distpath dist --workpath build --specpath build tools\gui.py > "%LOG%" 2>&1 || (
  type "%LOG%"
  echo.
  echo PyInstaller failed; the output above is its complete log, also saved as %LOG%.
  goto :fail
)
findstr /i /c:"WARNING" /c:"ERROR" "%LOG%"
if not exist "dist\EldenRingSuperRandomizer\EldenRingSuperRandomizer.exe" (
  echo.
  echo PyInstaller reported no error, but dist\EldenRingSuperRandomizer\EldenRingSuperRandomizer.exe does not exist. Most likely
  echo Windows Defender quarantined the fresh exe - PyInstaller programs are often false positives. Open
  echo "Windows Security - Virus and threat protection - Protection history", restore and allow it, or add this
  echo folder to the exclusions and run again.
  goto :fail
)
echo.
for %%F in (dist\EldenRingSuperRandomizer\EldenRingSuperRandomizer.exe) do echo built %%~fF  (%%~zF bytes)
echo Ship the whole dist\EldenRingSuperRandomizer folder: the exe, its DLLs and the data (paramdef, names, msg) all live
echo inside it.  The game's oo2core_6_win64.dll is not shipped; the user copies it from the game folder.
pause
exit /b 0

:fail
echo.
echo Failed, see the messages above.
pause
exit /b 1