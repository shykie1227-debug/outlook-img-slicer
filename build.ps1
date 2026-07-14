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

$manifestPath = Join-Path $projectRoot "build-manifest.json"
if (-not (Test-Path $manifestPath)) { Fail "Build manifest not found: $manifestPath" }
$manifest = Get-Content -Raw -Encoding UTF8 $manifestPath | ConvertFrom-Json
$exePath = $manifest.artifact_path
if ($manifest.artifact_kind -ne "onefile") { Fail "Release requires a onefile EXE." }
if (-not (Test-Path $exePath)) { Fail "Manifest artifact not found: $exePath" }
$actualHash = (Get-FileHash -Algorithm SHA256 $exePath).Hash.ToLowerInvariant()
if ($actualHash -ne $manifest.sha256) { Fail "Artifact hash does not match build manifest." }

$distDir = Join-Path $projectRoot "dist"
if (-not (Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir -Force | Out-Null
}
$releaseName = $manifest.release_filename
$releasePath = Join-Path $distDir $releaseName
Copy-Item -Path $exePath -Destination $releasePath -Force

$sizeMB = [math]::Round((Get-Item $releasePath).Length / 1MB, 1)

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  File: $releaseName" -ForegroundColor Green
Write-Host "  Size: $sizeMB MB" -ForegroundColor Green
Write-Host "  Path: $releasePath" -ForegroundColor Green
Write-Host "  SHA-256: $actualHash" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
