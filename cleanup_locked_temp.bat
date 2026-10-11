@echo off
setlocal
title Jakariya AI Studio - Clean Locked Temp Folders
echo ====================================================================
echo        Jakariya AI Studio - Locked Temp Folder Cleanup Tool
echo ====================================================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 goto :NOT_ADMIN

echo [INFO] Running with Administrator privileges...
cd /d "%~dp0"

echo [1/3] Taking ownership of locked folders...
takeown /f ".pytest-doc-attachment-final-temp" /r /d y >nul 2>&1
takeown /f ".pytest-doc-attachment-temp" /r /d y >nul 2>&1
takeown /f ".pytest-runtime-temp" /r /d y >nul 2>&1
for /d %%D in ("scratch\pytest-*") do (
    takeown /f "%%D" /r /d y >nul 2>&1
)

echo [2/3] Resetting permissions...
icacls ".pytest-doc-attachment-final-temp" /grant Everyone:(OI)(CI)F /t /c /q >nul 2>&1
icacls ".pytest-doc-attachment-temp" /grant Everyone:(OI)(CI)F /t /c /q >nul 2>&1
icacls ".pytest-runtime-temp" /grant Everyone:(OI)(CI)F /t /c /q >nul 2>&1
for /d %%D in ("scratch\pytest-*") do (
    icacls "%%D" /grant Everyone:(OI)(CI)F /t /c /q >nul 2>&1
)

echo [3/3] Removing locked folders...
rmdir /s /q ".pytest-doc-attachment-final-temp" >nul 2>&1
rmdir /s /q ".pytest-doc-attachment-temp" >nul 2>&1
rmdir /s /q ".pytest-runtime-temp" >nul 2>&1
for /d %%D in ("scratch\pytest-*") do (
    rmdir /s /q "%%D" >nul 2>&1
)

echo.
echo --------------------------------------------------------------------
if exist ".pytest-doc-attachment-final-temp" (
    echo [WARNING] .pytest-doc-attachment-final-temp still exists
) else (
    echo [SUCCESS] .pytest-doc-attachment-final-temp was deleted successfully
)

if exist ".pytest-doc-attachment-temp" (
    echo [WARNING] .pytest-doc-attachment-temp still exists
) else (
    echo [SUCCESS] .pytest-doc-attachment-temp was deleted successfully
)

if exist ".pytest-runtime-temp" (
    echo [WARNING] .pytest-runtime-temp still exists
) else (
    echo [SUCCESS] .pytest-runtime-temp was deleted successfully
)
echo --------------------------------------------------------------------
echo.
echo Process complete. You can now archive the folder with WinRAR.
echo ====================================================================
pause
exit /b 0

:NOT_ADMIN
echo [ERROR] Administrative privileges required!
echo.
echo Please follow these steps:
echo 1. Right-click on cleanup_locked_temp.bat
echo 2. Click "Run as administrator"
echo 3. Click "Yes" on the Windows prompt
echo.
pause
exit /b 1
