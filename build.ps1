<#
.SYNOPSIS
Outlook Image Slicer v6 - Build Script (Simple Version)

.DESCRIPTION
One-click build script for Windows. No parameters needed.
Just run and wait for the EXE file.

Output: release-artifacts\electron\*.exe
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $projectRoot

function Write-Step {
    param([int]$Num, [int]$Total, [string]$Title)
    Write-Host ""
    Write-Host "[$Num/$Total] $Title" -ForegroundColor Cyan
    Write-Host ("-" * 50) -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Msg)
    Write-Host "  [OK] " -ForegroundColor Green -NoNewline
    Write-Host $Msg
}

function Write-Err {
    param([string]$Msg)
    Write-Host "  [FAIL] " -ForegroundColor Red -NoNewline
    Write-Host $Msg
}

function Write-Info {
    param([string]$Msg)
    Write-Host "  [INFO] " -ForegroundColor Yellow -NoNewline
    Write-Host $Msg
}

function Fail {
    param([string]$Msg)
    Write-Host ""
    Write-Err $Msg
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Outlook Image Slicer v6 - Build" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This will build the Windows EXE file."
Write-Host "Estimated time: 5-10 minutes"
Write-Host ""

# Step 1: Find Node.js
Write-Step 1 8 "Finding Node.js..."

$nodePath = $null
$nodePaths = @(
    "$env:ProgramFiles\nodejs\node.exe",
    "${env:ProgramFiles(x86)}\nodejs\node.exe",
    "$env:LOCALAPPDATA\Programs\nodejs\node.exe"
)

foreach ($p in $nodePaths) {
    if (Test-Path $p) { $nodePath = $p; break }
}

if (-not $nodePath) {
    $n = Get-Command node -ErrorAction SilentlyContinue
    if ($n) { $nodePath = $n.Source }
}

if (-not $nodePath) {
    Fail "Node.js not found! Please install Node.js 18+ from https://nodejs.org/`n         Make sure to check 'Add to PATH' during installation."
}

$nodeVersion = & $nodePath --version
Write-Ok "Node.js $nodeVersion"

$nodeDir = Split-Path -Parent $nodePath
if (-not ($env:PATH -like "*$nodeDir*")) {
    $env:PATH = "$nodeDir;$env:PATH"
}

# Find npm via npm-cli.js (most reliable)
$npmCli = Join-Path $nodeDir "node_modules\npm\bin\npm-cli.js"
if (-not (Test-Path $npmCli)) {
    Fail "npm not found! Node.js installation may be incomplete."
}

$npmVersion = & $nodePath $npmCli --version
Write-Ok "npm $npmVersion"

# Step 2: Find Python
Write-Step 2 8 "Finding Python..."

$pythonPath = $null
$p = Get-Command python -ErrorAction SilentlyContinue
if ($p) { $pythonPath = $p.Source }

if (-not $pythonPath) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { $pythonPath = $py.Source }
}

if (-not $pythonPath) {
    $versions = @("314","313","312","311","310")
    foreach ($v in $versions) {
        $p = "$env:LOCALAPPDATA\Programs\Python\Python$v\python.exe"
        if (Test-Path $p) { $pythonPath = $p; break }
    }
}

if (-not $pythonPath) {
    Fail "Python not found! Please install Python 3.10+ from https://www.python.org/`n         Make sure to check 'Add Python to PATH' during installation."
}

$pyVersion = & $pythonPath --version
Write-Ok "Python $pyVersion"

# Step 3: Setup mirror for China
Write-Step 3 8 "Setting up download mirrors..."

& $nodePath $npmCli config set registry https://registry.npmmirror.com/ 2>&1 | Out-Null
& $nodePath $npmCli config set electron_mirror https://npmmirror.com/mirrors/electron/ 2>&1 | Out-Null
& $nodePath $npmCli config set electron-builder-binaries_mirror https://npmmirror.com/mirrors/electron-builder-binaries/ 2>&1 | Out-Null

$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

Write-Ok "Mirror configured (npmmirror.com)"

# Step 4: Install npm dependencies
Write-Step 4 8 "Installing npm dependencies..."

if (Test-Path "node_modules") {
    Write-Info "node_modules exists, skipping install"
} else {
    Write-Info "Running npm install (this may take 3-5 minutes)..."
    & $nodePath $npmCli install
    if ($LASTEXITCODE -ne 0) {
        Fail "npm install failed! Check your internet connection."
    }
    Write-Ok "npm dependencies installed"
}

# Step 5: Build renderer
Write-Step 5 8 "Building React renderer..."

& $nodePath $npmCli run build:renderer
if ($LASTEXITCODE -ne 0) {
    Fail "Renderer build failed!"
}
Write-Ok "Renderer built"

# Step 6: Build main process
Write-Step 6 8 "Building Electron main process..."

& $nodePath $npmCli run build:main
if ($LASTEXITCODE -ne 0) {
    Fail "Main process build failed!"
}
Write-Ok "Main process built"

# Step 7: Build Python sidecar
Write-Step 7 8 "Building Python sidecar (PyInstaller)..."

$sidecarDir = Join-Path $projectRoot "sidecar"
$sidecarDist = Join-Path $sidecarDir "dist"

if (Test-Path $sidecarDist) {
    Remove-Item -Recurse -Force $sidecarDist -ErrorAction SilentlyContinue
}

Write-Info "Running PyInstaller (this may take 1-2 minutes)..."

Push-Location $projectRoot
try {
    & $pythonPath -m PyInstaller --onefile --name sidecar_server `
        --distpath $sidecarDist --workpath "$sidecarDir\build" --specpath $sidecarDir `
        --noconfirm --clean --collect-all PIL --collect-all fitz --collect-all win32com `
        "$sidecarDir\sidecar_server.py" 2>&1 | Out-Null
} finally {
    Pop-Location
}

$sidecarExe = Join-Path $sidecarDist "sidecar_server.exe"
if (-not (Test-Path $sidecarExe)) {
    Fail "Sidecar build failed! Make sure PyInstaller is installed: pip install pyinstaller"
}
$sizeMB = (Get-Item $sidecarExe).Length / 1MB
Write-Ok "Sidecar built ($([math]::Round($sizeMB,1)) MB)"

# Step 8: Build Electron EXE
Write-Step 8 8 "Building Windows EXE (electron-builder)..."

Write-Info "Running electron-builder (this may take 3-5 minutes)..."

& $nodePath $npmCli run dist:win
if ($LASTEXITCODE -ne 0) {
    Fail "Electron build failed!"
}

# Verify result
$outDir = Join-Path $projectRoot "dist"
if (-not (Test-Path $outDir)) {
    Fail "Output directory not found!"
}

$exeFiles = Get-ChildItem -Path $outDir -Filter "*.exe"
if (-not $exeFiles -or $exeFiles.Count -eq 0) {
    Fail "No EXE file found in output!"
}

$resultExe = $exeFiles | Where-Object { $_.Name -like "*portable*" } | Select-Object -First 1
if (-not $resultExe) { $resultExe = $exeFiles | Select-Object -First 1 }

# Clean up: keep only the portable EXE, remove all other build artifacts
Write-Info "Cleaning up build artifacts..."
$keepFile = $resultExe.Name
Get-ChildItem -Path $outDir | Where-Object { $_.Name -ne $keepFile } | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}
Write-Ok "Kept only: $keepFile"

$finalSizeMB = (Get-Item $resultExe).Length / 1MB

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  File: $($resultExe.Name)" -ForegroundColor Green
Write-Host "  Size: $([math]::Round($finalSizeMB,1)) MB" -ForegroundColor Green
Write-Host "  Path: $($resultExe.FullName)" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
