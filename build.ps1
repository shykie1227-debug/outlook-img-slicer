<#
.SYNOPSIS
Outlook Image Slicer stable Windows build script.

.DESCRIPTION
Builds the desktop/PySide application through root build.py.
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $projectRoot

function Write-Step {
    param([string]$Title)
    Write-Host ""
    Write-Host $Title -ForegroundColor Cyan
    Write-Host ("-" * 50) -ForegroundColor Cyan
}

function Fail {
    param([string]$Msg)
    Write-Host ""
    Write-Host "[FAIL] $Msg" -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Outlook Image Slicer - Stable Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This builds the desktop/PySide EXE."
Write-Host ""

Write-Step "Finding Python..."

$pythonPath = $null
$cmd = Get-Command python -ErrorAction SilentlyContinue
if ($cmd) { $pythonPath = $cmd.Source }

if (-not $pythonPath) {
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { $pythonPath = $cmd.Source }
}

if (-not $pythonPath) {
    $versions = @("312","311","310")
    foreach ($v in $versions) {
        $candidate = "$env:LOCALAPPDATA\Programs\Python\Python$v\python.exe"
        if (Test-Path $candidate) {
            $pythonPath = $candidate
            break
        }
    }
}

if (-not $pythonPath) {
    Fail "Python not found. Please install Python 3.10+ and rerun build.bat."
}

$pythonVersion = & $pythonPath --version
Write-Host "[OK] $pythonVersion" -ForegroundColor Green

Write-Step "Building desktop/PySide EXE..."

$env:PYTHONIOENCODING = "utf-8"
$env:OUTLOOK_IMG_SLICER_NO_PAUSE = "1"
& $pythonPath (Join-Path $projectRoot "build.py")
if ($LASTEXITCODE -ne 0) {
    Fail "Build failed. See the log above."
}

$exePath = Join-Path $projectRoot "desktop\dist\OutlookImgSlicer.exe"
if (-not (Test-Path $exePath)) {
    $desktopDist = Join-Path $projectRoot "desktop\dist"
    $exeFiles = Get-ChildItem -Path $desktopDist -Filter "*.exe" -ErrorAction SilentlyContinue | Sort-Object Length -Descending
    if (-not $exeFiles -or $exeFiles.Count -eq 0) {
        Fail "EXE not found in $desktopDist"
    }
    $exePath = $exeFiles[0].FullName
}

$distDir = Join-Path $projectRoot "dist"
if (-not (Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir -Force | Out-Null
}
Copy-Item -Path $exePath -Destination (Join-Path $distDir "OutlookImgSlicer-V6.1.1.exe") -Force

$sizeMB = [math]::Round((Get-Item (Join-Path $distDir "OutlookImgSlicer-V6.1.1.exe")).Length / 1MB, 1)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  File: OutlookImgSlicer-V6.1.1.exe" -ForegroundColor Green
Write-Host "  Size: $sizeMB MB" -ForegroundColor Green
Write-Host "  Path: $distDir\OutlookImgSlicer-V6.1.1.exe" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
