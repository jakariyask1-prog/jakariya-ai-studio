param(
    [switch]$Clean = $false
)

$Host.UI.RawUI.WindowTitle = "Jakariya AI Studio - Single EXE Builder"
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "   Jakariya AI Studio - Single EXE Builder" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$pythonExe = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERROR] Python venv not found at $pythonExe" -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/2] Starting PyInstaller build on 'Jakariya AI Studio.spec'..." -ForegroundColor Yellow
Write-Host "Please wait, packaging files and compressing single EXE..." -ForegroundColor Gray

$argsList = @("Jakariya AI Studio.spec", "--noconfirm")
if ($Clean) {
    $argsList += "--clean"
}

& $pythonExe -m PyInstaller @argsList

if ($LASTEXITCODE -eq 0 -and (Test-Path "dist\Jakariya AI Studio.exe")) {
    $item = Get-Item "dist\Jakariya AI Studio.exe"
    $sizeMB = [math]::Round($item.Length / 1MB, 1)
    Write-Host "`n===================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] Single EXE Build Completed Successfully!" -ForegroundColor Green
    Write-Host " File: dist\Jakariya AI Studio.exe ($sizeMB MB)" -ForegroundColor Green
    Write-Host "===================================================" -ForegroundColor Green
} else {
    Write-Host "`n[ERROR] PyInstaller build failed." -ForegroundColor Red
    exit $LASTEXITCODE
}
