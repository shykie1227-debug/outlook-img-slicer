<#
.SYNOPSIS
Build the Outlook Image Slicer desktop EXE inside the Windows VM.

.DESCRIPTION
Runs in the local Parallels Windows VM, builds the PySide/PyInstaller desktop
application, and copies the final EXE back to the shared dist/ folder.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$SourceGitSha
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$SharedRoot = "\\Mac\Home\outlook-img-slicer"
$LocalRoot = "C:\build\outlook-img-slicer"
$LogFile = Join-Path $SharedRoot "vm_build.log"
$StatusFile = Join-Path $SharedRoot "vm_build_status.txt"
$buildStartedAt = [DateTime]::UtcNow

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

if ($SourceGitSha -notmatch '^[0-9a-fA-F]{40}$') {
    Fail "SourceGitSha must be the full 40-character commit SHA."
}
$env:OUTLOOK_IMG_SLICER_GIT_SHA = $SourceGitSha.ToLowerInvariant()
Write-Host "  Outlook Image Slicer - Desktop VM Build" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta

Write-Step "Step 0/7: Copy project to local directory"

# A previous onefile smoke test can leave its extracted child process alive and
# lock C:\build. Never allow that lock to turn a stale EXE into a false success.
Get-Process -Name "OutlookImgSlicer" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Info "Stopping previous OutlookImgSlicer test process (PID $($_.Id))..."
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500

if (Test-Path $LocalRoot) {
    Write-Info "Cleaning old local build directory..."
    Remove-Item -Recurse -Force $LocalRoot -ErrorAction SilentlyContinue
    if (Test-Path $LocalRoot) {
        Fail "Unable to clean local build directory: $LocalRoot"
    }
}

Write-Info "Copying source from shared folder..."
robocopy $SharedRoot $LocalRoot /E /XD dist release-artifacts build desktop\dist desktop\build /XF *.exe *.pdb /NJH /NJS /NP /NFL /NDL 2>&1 | Out-Null
$robocopyCode = $LASTEXITCODE

if ($robocopyCode -ge 8) {
    Fail "robocopy failed with exit code $robocopyCode"
}

if (-not (Test-Path $LocalRoot)) {
    Fail "robocopy failed - $LocalRoot not created"
}

Get-ChildItem -Path $LocalRoot -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    $_.Attributes = "Normal"
}

Write-Ok "Project copied to $LocalRoot"
Set-Location $LocalRoot

Write-Step "Step 1/7: Check Python"

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

Write-Step "Step 2/7: Install Python build/runtime dependencies"

& $pythonExe -m pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | Out-Null
& $pythonExe -m pip install Pillow PyMuPDF PySide6 pywin32 pyinstaller psd-tools numpy python-pptx lxml cairosvg svglib reportlab pytest dulwich -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "Python deps install failed"
}

$postInstall = Join-Path (Split-Path $pythonExe) "Scripts\pywin32_postinstall.py"
if (Test-Path $postInstall) {
    & $pythonExe $postInstall -install 2>&1 | Out-Null
}

$pyiVer = & $pythonExe -m PyInstaller --version 2>&1
Write-Ok "PyInstaller $pyiVer ready"

Write-Step "Step 3/7: Verify committed source and run Windows tests"

& $pythonExe (Join-Path $LocalRoot "verify_source_snapshot.py") $LocalRoot $SourceGitSha
if ($LASTEXITCODE -ne 0) {
    Fail "Copied source does not match a clean committed snapshot."
}

$env:QT_QPA_PLATFORM = "offscreen"
& $pythonExe -m pytest tests -q
if ($LASTEXITCODE -ne 0) {
    Fail "Windows pytest regression failed."
}
& $pythonExe -m compileall -q build.py desktop tests image_slicer.py html_assembler.py outlook_sender.py clipboard_html.py clickable_map.py hotspot_slicer.py image_safety.py pdf_slicer.py ppt_slicer.py psd_slicer.py
if ($LASTEXITCODE -ne 0) {
    Fail "Windows Python compile check failed."
}
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
Write-Ok "Committed source and Windows tests verified"

Write-Step "Step 4/7: Build desktop EXE"

$env:PYTHONIOENCODING = "utf-8"
$env:OUTLOOK_IMG_SLICER_NO_PAUSE = "1"
& $pythonExe (Join-Path $LocalRoot "build.py") 2>&1 | Tee-Object -FilePath (Join-Path $SharedRoot "build_step.log") -Append
if ($LASTEXITCODE -ne 0) {
    $tail = Get-Content (Join-Path $SharedRoot "build_step.log") -Tail 60 -ErrorAction SilentlyContinue
    "FAILED: Desktop PyInstaller build failed`n--- last 60 lines ---`n$($tail -join "`n")" | Out-File -FilePath $StatusFile -Force -Encoding ascii
    Stop-Transcript | Out-Null
    exit 1
}

$manifestPath = Join-Path $LocalRoot "build-manifest.json"
if (-not (Test-Path $manifestPath)) { Fail "Build manifest not found: $manifestPath" }
$manifest = Get-Content -Raw -Encoding UTF8 $manifestPath | ConvertFrom-Json
if ($manifest.artifact_kind -ne "onefile") { Fail "Release requires a onefile EXE." }
if ($manifest.git_sha -ne $env:OUTLOOK_IMG_SLICER_GIT_SHA) { Fail "Build manifest source commit does not match SourceGitSha." }
$resultExe = $manifest.artifact_path
if (-not (Test-Path $resultExe)) { Fail "Manifest artifact not found: $resultExe" }
$FinalExeName = $manifest.release_filename
$actualHash = (Get-FileHash -Algorithm SHA256 $resultExe).Hash.ToLowerInvariant()
if ($actualHash -ne $manifest.sha256) { Fail "Artifact hash does not match build manifest." }

$resultInfo = Get-Item $resultExe
if ($resultInfo.LastWriteTimeUtc -lt $buildStartedAt) {
    Fail "Build output is stale: $resultExe"
}

$sizeMB = [math]::Round($resultInfo.Length / 1MB, 1)
Write-Ok "Desktop EXE built ($sizeMB MB)"

Write-Step "Step 5/7: Verify PE version, startup and runtime network silence"

$fileVersion = $resultInfo.VersionInfo.FileVersion
if ($fileVersion -notlike "$($manifest.app_version).*") {
    Fail "PE FileVersion $fileVersion does not match app version $($manifest.app_version)."
}
$productVersion = $resultInfo.VersionInfo.ProductVersion
if ($productVersion -notlike "$($manifest.app_version).*") {
    Fail "PE ProductVersion $productVersion does not match app version $($manifest.app_version)."
}
Write-Ok "PE versions verified: FileVersion=$fileVersion ProductVersion=$productVersion"

$smokeProcess = Start-Process -FilePath $resultExe -PassThru
$networkViolation = $false
$networkAuditFailed = $false
$appProcesses = @()
for ($second = 0; $second -lt 45; $second++) {
    Start-Sleep -Seconds 1
    $appProcesses = @(Get-Process -Name "OutlookImgSlicer" -ErrorAction SilentlyContinue)
    if ($appProcesses.Count -eq 0) { continue }
    $appProcessIds = @($appProcesses | ForEach-Object { $_.Id })
    try {
        $networkConnections = @(
            Get-NetTCPConnection -ErrorAction Stop |
                Where-Object { $appProcessIds -contains $_.OwningProcess }
        )
    } catch {
        $networkAuditFailed = $true
        break
    }
    if ($networkConnections.Count -gt 0) {
        $networkViolation = $true
        break
    }
}
if ($appProcesses.Count -eq 0) {
    Fail "EXE startup smoke failed: OutlookImgSlicer process did not stay running."
}
$appProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
if ($networkAuditFailed) {
    Fail "Runtime network audit could not query TCP connections."
}
if ($networkViolation) {
    Fail "Runtime network audit found a TCP connection owned by OutlookImgSlicer."
}
Write-Ok "EXE startup and runtime network audit passed"

Write-Step "Step 6/7: Copy EXE to shared dist"

$sharedDist = Join-Path $SharedRoot "dist"
if (-not (Test-Path $sharedDist)) {
    New-Item -ItemType Directory -Path $sharedDist -Force | Out-Null
}

Get-ChildItem -Path $sharedDist -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}

Copy-Item -Path $resultExe -Destination (Join-Path $sharedDist $FinalExeName) -Force
Copy-Item -Path $manifestPath -Destination (Join-Path $SharedRoot "build-manifest.json") -Force
Write-Ok "EXE copied to $sharedDist"
Write-Ok "Build manifest copied to $SharedRoot"

Write-Step "Step 7/7: Done"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  File: $FinalExeName" -ForegroundColor Green
Write-Host "  Size: $sizeMB MB" -ForegroundColor Green
Write-Host "  Shared: $sharedDist\$FinalExeName" -ForegroundColor Green
Write-Host "  SHA-256: $actualHash" -ForegroundColor Green
Write-Host ""

"SUCCESS: $FinalExeName ($sizeMB MB)" | Out-File -FilePath $StatusFile -Force -Encoding ascii
Stop-Transcript | Out-Null
exit 0
