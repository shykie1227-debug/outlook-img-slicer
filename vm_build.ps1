<#
.SYNOPSIS
Build the Outlook Image Slicer desktop EXE inside the Windows VM.

.DESCRIPTION
Runs in the local Parallels Windows VM, builds the PySide/PyInstaller desktop
application, and copies the final EXE back to the shared dist/ folder.
#>

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$SharedRoot = "\\Mac\Home\outlook-img-slicer"
$LocalRoot = "C:\build\outlook-img-slicer"
$LogFile = Join-Path $SharedRoot "vm_build.log"
$StatusFile = Join-Path $SharedRoot "vm_build_status.txt"
$FinalExeName = "OutlookImgSlicer-V6.1.1.exe"

Start-Transcript -Path $LogFile -Force | Out-Null

function Write-Step($msg) {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
}

function Write-Ok($msg) {
    Write-Host "  [OK] $msg" -ForegroundColor Green
}

function Write-Info($msg) {
    Write-Host "  [INFO] $msg" -ForegroundColor Yellow
}

function Write-Err($msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
}

function Fail($msg) {
    Write-Err $msg
    "FAILED: $msg" | Out-File -FilePath $StatusFile -Force -Encoding ascii
    Stop-Transcript | Out-Null
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  Outlook Image Slicer - Desktop VM Build" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta

Write-Step "Step 0/5: Copy project to local directory"

if (Test-Path $LocalRoot) {
    Write-Info "Cleaning old local build directory..."
    Remove-Item -Recurse -Force $LocalRoot -ErrorAction SilentlyContinue
}

Write-Info "Copying source from shared folder..."
robocopy $SharedRoot $LocalRoot /E /XD dist .git release-artifacts build desktop\dist desktop\build /XF *.exe *.pdb /NJH /NJS /NP /NFL /NDL 2>&1 | Out-Null

if (-not (Test-Path $LocalRoot)) {
    Fail "robocopy failed - $LocalRoot not created"
}

Get-ChildItem -Path $LocalRoot -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    $_.Attributes = "Normal"
}

Write-Ok "Project copied to $LocalRoot"
Set-Location $LocalRoot

Write-Step "Step 1/5: Check Python"

$pythonExe = $null
$pyCandidates = @(
    "C:\Program Files\Python312\python.exe",
    "C:\Program Files\Python311\python.exe",
    "C:\Program Files\Python310\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
)

foreach ($p in $pyCandidates) {
    if (Test-Path $p) {
        $pythonExe = $p
        break
    }
}

if (-not $pythonExe) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $pythonExe = $cmd.Source }
}

if (-not $pythonExe) {
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) {
        try {
            $pyResult = & $cmd.Source -c "import sys; print(sys.executable)" 2>$null
            if ($pyResult -and (Test-Path $pyResult)) {
                $pythonExe = $pyResult
            }
        } catch {
            Write-Info "py launcher exists but no Python installed"
        }
    }
}

if ($pythonExe -and (Test-Path $pythonExe)) {
    $pyVer = & $pythonExe --version 2>&1
    Write-Ok "Python installed: $pyVer"
} else {
    Write-Info "Python not found, downloading Python 3.12.7..."
    $pythonUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
    $installer = Join-Path $env:TEMP "python-3.12.7-installer.exe"
    try {
        Invoke-WebRequest -Uri $pythonUrl -OutFile $installer -UseBasicParsing -TimeoutSec 120
    } catch {
        $mirrorUrl = "https://mirrors.huaweicloud.com/python/3.12.7/python-3.12.7-amd64.exe"
        Invoke-WebRequest -Uri $mirrorUrl -OutFile $installer -UseBasicParsing -TimeoutSec 120
    }
    $proc = Start-Process -FilePath $installer -ArgumentList "/quiet","InstallAllUsers=1","PrependPath=1","Include_pip=1" -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Fail "Python install failed (exit code: $($proc.ExitCode))"
    }
    $machinePath = [System.Environment]::GetEnvironmentVariable("PATH","Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("PATH","User")
    $env:PATH = "$machinePath;$userPath"
    $pythonExe = "C:\Program Files\Python312\python.exe"
    if (-not (Test-Path $pythonExe)) {
        Fail "Python still not found after install"
    }
    $pyVer = & $pythonExe --version 2>&1
    Write-Ok "Python installed: $pyVer"
}

Write-Step "Step 2/5: Install Python build/runtime dependencies"

& $pythonExe -m pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | Out-Null
& $pythonExe -m pip install Pillow PyMuPDF PySide6 pywin32 pyinstaller psd-tools numpy python-pptx lxml cairosvg svglib reportlab -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "Python deps install failed"
}

$postInstall = Join-Path (Split-Path $pythonExe) "Scripts\pywin32_postinstall.py"
if (Test-Path $postInstall) {
    & $pythonExe $postInstall -install 2>&1 | Out-Null
}

$pyiVer = & $pythonExe -m PyInstaller --version 2>&1
Write-Ok "PyInstaller $pyiVer ready"

Write-Step "Step 3/5: Build desktop EXE"

$env:PYTHONIOENCODING = "utf-8"
$env:OUTLOOK_IMG_SLICER_NO_PAUSE = "1"
& $pythonExe (Join-Path $LocalRoot "build.py") 2>&1 | Tee-Object -FilePath (Join-Path $SharedRoot "build_step.log") -Append
if ($LASTEXITCODE -ne 0) {
    $tail = Get-Content (Join-Path $SharedRoot "build_step.log") -Tail 60 -ErrorAction SilentlyContinue
    "FAILED: Desktop PyInstaller build failed`n--- last 60 lines ---`n$($tail -join "`n")" | Out-File -FilePath $StatusFile -Force -Encoding ascii
    Stop-Transcript | Out-Null
    exit 1
}

$desktopDist = Join-Path $LocalRoot "desktop\dist"
$resultExe = Join-Path $desktopDist "OutlookImgSlicer.exe"
if (-not (Test-Path $resultExe)) {
    $exeFiles = Get-ChildItem -Path $desktopDist -Filter "*.exe" -ErrorAction SilentlyContinue | Sort-Object Length -Descending
    if (-not $exeFiles -or $exeFiles.Count -eq 0) {
        Fail "Desktop EXE not found in $desktopDist"
    }
    $resultExe = $exeFiles[0].FullName
}

$sizeMB = [math]::Round((Get-Item $resultExe).Length / 1MB, 1)
Write-Ok "Desktop EXE built ($sizeMB MB)"

Write-Step "Step 4/5: Copy EXE to shared dist"

$sharedDist = Join-Path $SharedRoot "dist"
if (-not (Test-Path $sharedDist)) {
    New-Item -ItemType Directory -Path $sharedDist -Force | Out-Null
}

Get-ChildItem -Path $sharedDist -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}

Copy-Item -Path $resultExe -Destination (Join-Path $sharedDist $FinalExeName) -Force
Write-Ok "EXE copied to $sharedDist"

Write-Step "Step 5/5: Done"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  File: $FinalExeName" -ForegroundColor Green
Write-Host "  Size: $sizeMB MB" -ForegroundColor Green
Write-Host "  Shared: $sharedDist\$FinalExeName" -ForegroundColor Green
Write-Host ""

"SUCCESS: $FinalExeName ($sizeMB MB)" | Out-File -FilePath $StatusFile -Force -Encoding ascii
Stop-Transcript | Out-Null
exit 0
