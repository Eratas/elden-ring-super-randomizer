@echo off
rem Pack the window into one executable: dist\EldenRingSuperRandomizer.exe (PyInstaller).
rem tools\paramdef and tools\names go inside the exe; tools\msg\engus\item_dlc02.msgbnd.dcx (the weapon names) is
rem copied next to it as dist\msg\engus\..., because it is a text archive the game loads, not a Python file.
rem oo2core_6_win64.dll does not: keep it next to the exe or pick it in the window.
rem The DLL is never shipped - it is RAD Game Tools' and comes with the game - the user copies it from the game folder.
rem Every failure stops with a pause so the error can be read (the window does not just flash and close).
rem All messages are ASCII on purpose: cmd shows UTF-8 text as garbage in the default code page.
rem No parentheses inside echo lines within ( ) blocks: an unescaped ) there ends the block and kills the script.
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
rem tools\tkcheck.py makes sure Tk works and prints TCL_LIBRARY / TK_LIBRARY as NAME=value lines: a Python that
rem cannot find init.tcl from inside a venv would produce an exe without a window, and PyInstaller's tkinter hook
rem needs the two variables to put the Tcl/Tk script libraries into the exe.  The values are parsed straight into
rem the environment, so no temporary script file is written to disk (which antivirus may flag as a dropper).
rem --version-file embeds Windows PE version metadata (company, product, version) into the exe: a generic,
rem metadata-less PyInstaller binary is exactly what AV heuristics and SmartScreen flag hardest, so this measurably
rem reduces false positives.  Signing the exe (signtool) is the stronger measure; see README "Antivirus notes".
set "TCL_LIBRARY="
set "TK_LIBRARY="
for /f "tokens=1,* delims==" %%A in ('"%VENV%\Scripts\python.exe" -I tools\tkcheck.py') do set "%%A=%%B"
if not defined TCL_LIBRARY if not defined TK_LIBRARY (
  echo.
  echo This virtual environment's Python has no usable tkinter; the packed exe would have no window. Stopped.
  echo Install Python from python.org with "tcl/tk and IDLE" ticked, delete %VENV% and run this script again.
  goto :fail
)
echo TCL_LIBRARY=%TCL_LIBRARY%
echo TK_LIBRARY=%TK_LIBRARY%
"%VENV%\Scripts\python.exe" -c "import PyInstaller" >nul 2>&1 || (
  echo Installing PyInstaller into %VENV% ...
  "%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check pyinstaller || goto :fail
)
rem PyInstaller's full output goes to build\pyinstaller.log (send that file when something goes wrong);
rem on failure it is shown in full.
if not exist build mkdir build
set "LOG=%~dp0build\pyinstaller.log"
echo Packing, this takes a minute or two; the full output is written to %LOG% ...
"%VENV%\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name EldenRingSuperRandomizer ^
  --version-file "%~dp0tools\version_info.txt" ^
  --hidden-import test_logic ^
  --add-data "%~dp0tools\paramdef;paramdef" --add-data "%~dp0tools\names;names" ^
  --distpath dist --workpath build --specpath build tools\gui.py > "%LOG%" 2>&1 || (
  type "%LOG%"
  echo.
  echo PyInstaller failed; the output above is its complete log, also saved as %LOG%.
  goto :fail
)
findstr /i /c:"WARNING" /c:"ERROR" "%LOG%"
if not exist "dist\EldenRingSuperRandomizer.exe" (
  echo.
  echo PyInstaller reported no error, but dist\EldenRingSuperRandomizer.exe does not exist. Most likely Windows Defender
  echo quarantined the fresh exe - PyInstaller programs are often false positives. Open "Windows Security -
  echo Virus and threat protection - Protection history", restore and allow EldenRingSuperRandomizer.exe, or add this
  echo folder to the exclusions and run this script again. If the history shows nothing, send %LOG%.
  goto :fail
)
for /d %%L in (tools\msg\*) do (
  if exist "%%L\item_dlc02.msgbnd.dcx" (
    if not exist "dist\msg\%%~nxL" mkdir "dist\msg\%%~nxL"
    copy /y "%%L\item_dlc02.msgbnd.dcx" "dist\msg\%%~nxL\" >nul || goto :fail
  )
)
echo.
for %%F in (dist\EldenRingSuperRandomizer.exe) do echo built %%~fF  (%%~zF bytes)
dir /b /s dist\msg
echo Upload EldenRingSuperRandomizer.exe together with the msg folder: the weapon names read msg\^<language^>\item_dlc02 next to the exe.
echo The game's oo2core_6_win64.dll is not shipped; users copy it from the game folder.
echo If double-clicking it shows no window, the error is shown in a message box.
pause
exit /b 0

:fail
echo.
echo Failed, see the messages above.
echo Common causes: no Python 3.10-3.14 - install Python 3.14 from python.org (tick "tcl/tk and IDLE") and run
echo again; or a package download failed - check the network and retry.
pause
exit /b 1