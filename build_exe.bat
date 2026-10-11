@echo off
title Jakariya AI Studio - Build Single EXE
echo ===================================================
echo   Jakariya AI Studio - Building Single EXE
echo ===================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment python not found at .venv\Scripts\python.exe
    pause
    exit /b 1
)

set CLEAN_FLAG=
if "%1"=="--clean" set CLEAN_FLAG=--clean
if "%1"=="clean" set CLEAN_FLAG=--clean

echo Starting PyInstaller build %CLEAN_FLAG%...
".venv\Scripts\python.exe" -m PyInstaller "Jakariya AI Studio.spec" --noconfirm %CLEAN_FLAG%

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===================================================
    echo   [SUCCESS] Single EXE Build Complete!
    echo   Output: dist\Jakariya AI Studio.exe
    echo ===================================================
) else (
    echo.
    echo ===================================================
    echo   [ERROR] Build failed with exit code %ERRORLEVEL%
    echo ===================================================
)
echo.
pause
