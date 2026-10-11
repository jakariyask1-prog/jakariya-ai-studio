# Jakariya AI Studio - Clean Locked Temp Folders (PowerShell)
$ErrorActionPreference = "SilentlyContinue"

$targetPaths = @(
    Join-Path $PSScriptRoot ".pytest-doc-attachment-final-temp",
    Join-Path $PSScriptRoot ".pytest-doc-attachment-temp",
    Join-Path $PSScriptRoot ".pytest-runtime-temp"
)
$scratchLocked = Get-ChildItem -Path (Join-Path $PSScriptRoot "scratch") -Directory -Filter "pytest-*" -ErrorAction SilentlyContinue
if ($scratchLocked) {
    $targetPaths += $scratchLocked.FullName
}

Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host "       Jakariya AI Studio - Locked Temp Folder Cleanup Tool         " -ForegroundColor Cyan
Write-Host "====================================================================" -ForegroundColor Cyan
Write-Host ""

foreach ($p in $targetPaths) {
    if (Test-Path -LiteralPath $p) {
        Write-Host "Unlocking: $p"
        & takeown.exe /f $p /r /d y 2>$null | Out-Null
        & icacls.exe $p /grant "*S-1-1-0:(OI)(CI)F" /t /c /q 2>$null | Out-Null
        
        Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $p) {
            & cmd.exe /c "rmdir /s /q `"$p`"" 2>$null | Out-Null
        }

        if (Test-Path -LiteralPath $p) {
            Write-Host "  [X] Failed to delete: $(Split-Path $p -Leaf)" -ForegroundColor Red
        } else {
            Write-Host "  [✓] Successfully deleted: $(Split-Path $p -Leaf)" -ForegroundColor Green
        }
    } else {
        Write-Host "  [-] Already gone: $(Split-Path $p -Leaf)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Done! You can now archive the project with WinRAR without issues." -ForegroundColor Cyan
Write-Host "Press Enter to exit..."
Read-Host
