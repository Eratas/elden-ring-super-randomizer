@echo off
rem One command to check everything: the portable gate, then (if a real regulation.bin is found) the
rem real-file fuzz + conservation pass (erreg, dropshuffle, enemy_drops, weapons, gems, spells).
rem Exit 0 = all green, 1 = a check failed.  Run from anywhere.
rem   tools\selfcheck.bat                                  auto-detects a regulation.bin
rem   set ER_REGULATION_BIN=C:\path\to\regulation.bin & tools\selfcheck.bat   point at a specific file
rem A KRAK regulation needs the game's oo2core_6_win64.dll; it is looked up next to the regulation and
rem in the usual Elden Ring folders.  Without a regulation (or its DLL) only the portable gate runs.
setlocal
set "PY=python"
if exist "%USERPROFILE%\.venvs\er_mod\Scripts\python.exe" set "PY=%USERPROFILE%\.venvs\er_mod\Scripts\python.exe"

echo === gate ===
"%PY%" "%~dp0gate.py"
if errorlevel 1 (
  echo.
  echo SELFCHECK FAIL - gate
  exit /b 1
)

rem locate a real regulation.bin for the real-file fuzz
set "REG="
if defined ER_REGULATION_BIN if exist "%ER_REGULATION_BIN%" set "REG=%ER_REGULATION_BIN%"
if not defined REG if exist "C:\Games\ERR\mod\regulation.bin" set "REG=C:\Games\ERR\mod\regulation.bin"
if not defined REG if exist "C:\Games\ELDEN RING\Game\regulation.bin" set "REG=C:\Games\ELDEN RING\Game\regulation.bin"
if not defined REG (
  echo.
  echo SELFCHECK PASS - portable gate only ^(no regulation.bin found; set ER_REGULATION_BIN for the real-file fuzz^)
  exit /b 0
)

rem oo2core_6_win64.dll: the game's own, next to the regulation, or in the ERR deploy folder
if not defined OODLE_DLL if exist "C:\Games\ELDEN RING\Game\oo2core_6_win64.dll" set "OODLE_DLL=C:\Games\ELDEN RING\Game\oo2core_6_win64.dll"
if not defined OODLE_DLL for %%D in ("%REG%\..\oo2core_6_win64.dll") do if exist "%%~fD" set "OODLE_DLL=%%~fD"
if not defined OODLE_DLL for %%D in ("%REG%\..\menu\deploy\oo2core_6_win64.dll") do if exist "%%~fD" set "OODLE_DLL=%%~fD"

echo === real-file fuzz + conservation on %REG% ===
"%PY%" "%~dp0test_logic.py" --fuzz "%REG%"
if errorlevel 1 (
  echo.
  echo SELFCHECK FAIL - real-file fuzz
  exit /b 1
)

echo.
echo SELFCHECK PASS - gate + real-file fuzz
exit /b 0