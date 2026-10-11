@echo off
setlocal
title Jakariya AI Studio - One-Click RAR Creator
echo ====================================================================
echo        Jakariya AI Studio - One-Click RAR Archive Creator
echo ====================================================================
echo.

set "WINRAR_PATH=C:\Program Files\WinRAR\Rar.exe"
if not exist "%WINRAR_PATH%" goto :NO_WINRAR

cd /d "%~dp0"
set "OUTPUT_RAR=..\jakariya-AI-studio-model.rar"

echo Creating RAR archive: %OUTPUT_RAR%
echo Excluding locked pytest temp folders and cache...
echo.

"%WINRAR_PATH%" a -r -x"*.pytest*" -x"*pytest-*" -x".pytest*" -x".venv\*" -x".gemini\*" -x".agents\*" -x"*.pyc" -x"__pycache__\*" -x"temp_*" "%OUTPUT_RAR%" *

if %errorLevel% equ 0 goto :SUCCESS
goto :FAILED

:SUCCESS
echo.
echo --------------------------------------------------------------------
echo [SUCCESS] RAR archive created successfully:
echo %OUTPUT_RAR%
echo --------------------------------------------------------------------
echo.
pause
exit /b 0

:FAILED
echo.
echo --------------------------------------------------------------------
echo [ERROR] Failed to create RAR archive. Error Code: %errorLevel%
echo --------------------------------------------------------------------
echo.
pause
exit /b 1

:NO_WINRAR
echo [ERROR] WinRAR not found at: %WINRAR_PATH%
echo.
pause
exit /b 1
