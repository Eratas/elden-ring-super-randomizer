@echo off
rem Prints the command that runs a Python this project can use (3.10 to 3.14: the dependencies have no
rem wheels for 3.15 yet).  Nothing is printed and the exit code is 1 when there is none.
rem Used by randomize.bat, randomize_gui.bat and build_exe.bat through:
rem     for /f "delims=" %%P in ('tools\findpython.bat') do set "PY=%%P"
rem All messages are ASCII on purpose: cmd shows UTF-8 text as garbage in the default code page.
rem No parentheses inside echo lines within ( ) blocks: an unescaped ) there ends the block and kills the script.
for %%V in (3.14 3.13 3.12 3.11 3.10) do (
  py -%%V -c "import sys" >nul 2>&1 && (
    echo py -%%V
    exit /b 0
  )
)
py -3 -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>&1 && (
  echo py -3
  exit /b 0
)
python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,15) else 1)" >nul 2>&1 && (
  echo python
  exit /b 0
)
exit /b 1