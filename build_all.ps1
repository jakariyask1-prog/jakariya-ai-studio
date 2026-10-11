# ==============================================================================
# build_all.ps1  --  Full build pipeline for Jakariya AI Studio
# Builds:
#   1. dist\Jakariya AI Studio\   (folder/COLLECT build via main.spec)
#   2. dist\Jakariya AI Studio.exe (one-file build via "Jakariya AI Studio.spec")
#   3. dist\Jakariya_AI_Studio_Setup_v2.0.0.exe  (Inno Setup installer)
# ==============================================================================

Set-StrictMode -Off
$ErrorActionPreference = "Stop"

$proj    = $PSScriptRoot
$venvPy  = Join-Path $proj ".venv\Scripts\python.exe"
$pyinst  = Join-Path $proj ".venv\Scripts\pyinstaller.exe"
$iscc    = $null

function Log($msg) { Write-Host "`n[$([datetime]::Now.ToString('HH:mm:ss'))] $msg" -ForegroundColor Cyan }
function OK($msg)  { Write-Host "  OK: $msg" -ForegroundColor Green }
function ERR($msg) { Write-Host "  ERROR: $msg" -ForegroundColor Red; exit 1 }

# 0. Verify prerequisites
Log "Checking prerequisites..."
if (-not (Test-Path $venvPy)) { ERR "Python venv not found at $venvPy" }
OK "Python venv: $venvPy"
if (-not (Test-Path $pyinst)) { $pyinst = $null }

# 1. Download & Install Inno Setup 6 silently
Log "Checking for Inno Setup..."
$isccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
    "C:\Program Files\Inno Setup 7\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe"
)
$iscc = $isccPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    Log "Inno Setup not found. Installing via winget..."
    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { ERR "winget install failed (exit $LASTEXITCODE). Install Inno Setup manually from https://www.jrsoftware.org/isdl.php" }
    # Refresh environment PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")
    Start-Sleep -Seconds 3
    $iscc = $isccPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) { ERR "ISCC.exe not found after winget install. Please restart PowerShell and re-run." }
    OK "Inno Setup installed: $iscc"
} else {
    OK "Inno Setup already installed: $iscc"
}

# 2. Clean dist\
Log "Cleaning old dist\ output..."
$distDir = Join-Path $proj "dist"
if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force; OK "Removed old dist\" }

# 3. Folder build (main.spec)
Log "Building FOLDER layout (main.spec)..."
$specFolder = Join-Path $proj "main.spec"
if (-not (Test-Path $specFolder)) { ERR "main.spec not found" }
if ($pyinst) {
    & $pyinst $specFolder --noconfirm
} else {
    & $venvPy -m PyInstaller $specFolder --noconfirm
}
if ($LASTEXITCODE -ne 0) { ERR "PyInstaller (main.spec) failed" }
$folderBuild = Join-Path $distDir "Jakariya AI Studio"
if (-not (Test-Path $folderBuild)) { ERR "Folder build not produced: $folderBuild" }
OK "Folder build ready: $folderBuild"

# 4. Single-file EXE ("Jakariya AI Studio.spec")
Log "Building SINGLE-FILE EXE..."
$specOnefile = Join-Path $proj "Jakariya AI Studio.spec"
if (-not (Test-Path $specOnefile)) { ERR "'Jakariya AI Studio.spec' not found" }
if ($pyinst) {
    & $pyinst $specOnefile --noconfirm
} else {
    & $venvPy -m PyInstaller $specOnefile --noconfirm
}
if ($LASTEXITCODE -ne 0) { ERR "PyInstaller (Jakariya AI Studio.spec) failed" }
$onefileExe = Join-Path $distDir "Jakariya AI Studio.exe"
if (-not (Test-Path $onefileExe)) { ERR "Single-file EXE not produced: $onefileExe" }
OK "Single-file EXE: $onefileExe ($([math]::Round((Get-Item $onefileExe).Length/1MB,1)) MB)"

# 5. Compile Inno Setup installer
Log "Compiling Inno Setup installer..."
$issFile = Join-Path $proj "Jakariya_AI_Studio_Setup.iss"
if (-not (Test-Path $issFile)) { ERR "ISS script not found: $issFile" }
& $iscc $issFile
if ($LASTEXITCODE -ne 0) { ERR "ISCC.exe failed" }
$setupExe = Join-Path $distDir "Jakariya_AI_Studio_Setup_v2.0.0.exe"
if (-not (Test-Path $setupExe)) { ERR "Setup EXE not found: $setupExe" }
OK "Installer: $setupExe ($([math]::Round((Get-Item $setupExe).Length/1MB,1)) MB)"

# 6. Summary
Log "BUILD COMPLETE"
Write-Host "`n  Outputs in dist\" -ForegroundColor Yellow
Get-ChildItem $distDir | ForEach-Object {
    $size = if ($_.PSIsContainer) {
        "$([math]::Round((Get-ChildItem $_.FullName -Recurse -File | Measure-Object Length -Sum).Sum/1MB,1)) MB (folder)"
    } else {
        "$([math]::Round($_.Length/1MB,1)) MB"
    }
    Write-Host "    $($_.Name)  [$size]" -ForegroundColor White
}


