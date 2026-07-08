<#
.SYNOPSIS
VM build script for Outlook Image Slicer V6 (runs inside Windows VM via Parallels)

.DESCRIPTION
Runs inside Windows VM. Steps:
1. Copy project from Parallels shared folder to local C:\build (exclude node_modules)
2. Install Python, PyInstaller, npm deps
3. Build complete EXE
4. Copy result back to shared folder dist/
#>

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# Paths
$SharedRoot = "\\Mac\Home\Documents\outlook-img-slicer"
$LocalRoot = "C:\build\outlook-img-slicer"
$LogFile = Join-Path $SharedRoot "vm_build.log"

# Start transcript log (written to shared folder, readable from macOS)
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
    Write-Host ""
    Write-Host ">>>> BUILD FAILED <<<<" -ForegroundColor Red
    "FAILED: $msg" | Out-File -FilePath "\\Mac\Home\Documents\outlook-img-slicer\vm_build_status.txt" -Force -Encoding ascii
    Stop-Transcript | Out-Null
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  Outlook Image Slicer V6 - VM Build" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta

# Step 0: Copy project to local (shared folder not suitable for npm install)
Write-Step "Step 0/8: Copy project to local directory"

if (Test-Path $LocalRoot) {
    Write-Info "Cleaning old local build directory..."
    Remove-Item -Recurse -Force $LocalRoot -ErrorAction SilentlyContinue
}

Write-Info "Copying from shared folder (exclude node_modules, dist, .git)..."
robocopy $SharedRoot $LocalRoot /E /XD node_modules dist .git release-artifacts sidecar\dist sidecar\build /XF *.exe *.pdb /NJH /NJS /NP /NFL /NDL 2>&1 | Out-Null

if (-not (Test-Path $LocalRoot)) {
    Fail "robocopy failed - $LocalRoot not created"
}

# Fix file attributes (robocopy may set read-only on copied files)
Write-Info "Resetting file attributes..."
Get-ChildItem -Path $LocalRoot -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    $_.Attributes = "Normal"
}
# Remove package-lock.json (npm install will regenerate it, avoids EPERM on stale lock)
Remove-Item -Path (Join-Path $LocalRoot "package-lock.json") -Force -ErrorAction SilentlyContinue

Write-Ok "Project copied to $LocalRoot"

Set-Location $LocalRoot

# Step 1: Check / Install Python
Write-Step "Step 1/8: Check Python"

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
        Write-Info "Official source failed, trying mirror..."
        $mirrorUrl = "https://mirrors.huaweicloud.com/python/3.12.7/python-3.12.7-amd64.exe"
        Invoke-WebRequest -Uri $mirrorUrl -OutFile $installer -UseBasicParsing -TimeoutSec 120
    }

    Write-Info "Silent installing Python..."
    $proc = Start-Process -FilePath $installer -ArgumentList "/quiet","InstallAllUsers=1","PrependPath=1","Include_pip=1" -Wait -PassThru

    if ($proc.ExitCode -ne 0) {
        Fail "Python install failed (exit code: $($proc.ExitCode))"
    }

    # Refresh PATH
    $machinePath = [System.Environment]::GetEnvironmentVariable("PATH","Machine")
    $userPath = [System.Environment]::GetEnvironmentVariable("PATH","User")
    $env:PATH = "$machinePath;$userPath"

    $pythonExe = "C:\Program Files\Python312\python.exe"
    if (-not (Test-Path $pythonExe)) {
        $cmd = Get-Command python -ErrorAction SilentlyContinue
        if ($cmd) { $pythonExe = $cmd.Source }
    }

    if (-not $pythonExe -or -not (Test-Path $pythonExe)) {
        Fail "Python still not found after install"
    }

    $pyVer = & $pythonExe --version 2>&1
    Write-Ok "Python installed: $pyVer"
}

# Step 2: Install Python deps + PyInstaller
Write-Step "Step 2/8: Install Python deps + PyInstaller"

Write-Info "Upgrading pip (China mirror)..."
& $pythonExe -m pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | Out-Null

Write-Info "Installing pillow PyMuPDF pywin32 pyinstaller (China mirror)..."
& $pythonExe -m pip install pillow PyMuPDF pywin32 pyinstaller -q -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Fail "Python deps install failed"
}

# pywin32 postinstall
$postInstall = Join-Path (Split-Path $pythonExe) "Scripts\pywin32_postinstall.py"
if (Test-Path $postInstall) {
    & $pythonExe $postInstall -install 2>&1 | Out-Null
}

$pyiVer = & $pythonExe -m PyInstaller --version 2>&1
Write-Ok "PyInstaller $pyiVer ready"

# Step 3: Check Node.js + npm
Write-Step "Step 3/8: Check Node.js"

$nodeExe = $null
$cmd = Get-Command node -ErrorAction SilentlyContinue
if ($cmd) { $nodeExe = $cmd.Source }

if (-not $nodeExe) {
    $nodeCandidates = @(
        "C:\Program Files\nodejs\node.exe",
        "$env:LOCALAPPDATA\Programs\nodejs\node.exe"
    )
    foreach ($p in $nodeCandidates) {
        if (Test-Path $p) { $nodeExe = $p; break }
    }
}

if (-not $nodeExe) {
    Write-Info "Node.js not found, downloading Node.js v20.18.0 LTS..."

    $nodeUrl = "https://mirrors.huaweicloud.com/nodejs/v20.18.0/node-v20.18.0-x64.msi"
    $nodeMsi = Join-Path $env:TEMP "node-v20.18.0-x64.msi"

    try {
        Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeMsi -UseBasicParsing -TimeoutSec 300
    } catch {
        $officialUrl = "https://nodejs.org/dist/v20.18.0/node-v20.18.0-x64.msi"
        Invoke-WebRequest -Uri $officialUrl -OutFile $nodeMsi -UseBasicParsing -TimeoutSec 300
    }

    Write-Info "Silent installing Node.js..."
    $proc = Start-Process -FilePath "msiexec.exe" -ArgumentList "/i",$nodeMsi,"/quiet","/norestart" -Wait -PassThru

    if ($proc.ExitCode -ne 0) {
        Fail "Node.js install failed (exit code: $($proc.ExitCode))"
    }

    $machinePath = [System.Environment]::GetEnvironmentVariable("PATH","Machine")
    $env:PATH = "$machinePath;$env:PATH"

    $nodeExe = "C:\Program Files\nodejs\node.exe"
    if (-not (Test-Path $nodeExe)) {
        Fail "Node.js still not found after install"
    }
}

$nodeVer = & $nodeExe --version 2>&1
Write-Ok "Node.js $nodeVer"

$nodeDir = Split-Path -Parent $nodeExe
$npmCli = Join-Path $nodeDir "node_modules\npm\bin\npm-cli.js"
if (-not (Test-Path $npmCli)) {
    Fail "npm not found, Node.js install may be incomplete"
}

Write-Info "Configuring China npm mirror..."
& $nodeExe $npmCli config set registry https://registry.npmmirror.com/ 2>&1 | Out-Null

# Electron mirrors are set as env vars (not npm config - npm v24 rejects them)
$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

$npmVer = & $nodeExe $npmCli --version 2>&1
Write-Ok "npm $npmVer (China mirror configured)"

# Step 4: Install npm deps
Write-Step "Step 4/8: Install npm deps"

Write-Info "Running npm install (may take 3-5 minutes)..."
& $nodeExe $npmCli install 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "npm install failed"
}

$env:PATH = (Join-Path $LocalRoot "node_modules\.bin") + ";" + $env:PATH

Write-Ok "npm deps installed"

# Step 5: Build React renderer + Electron main
Write-Step "Step 5/8: Build renderer + main process"

Write-Info "Building React renderer..."
& $nodeExe $npmCli run build:renderer 2>&1 | Tee-Object -FilePath (Join-Path $SharedRoot "build_step.log") -Append
if ($LASTEXITCODE -ne 0) {
    $tail = Get-Content (Join-Path $SharedRoot "build_step.log") -Tail 40 -ErrorAction SilentlyContinue
    "FAILED: React renderer build failed`n--- last 40 lines ---`n$($tail -join "`n")" | Out-File -FilePath (Join-Path $SharedRoot "vm_build_status.txt") -Force -Encoding ascii
    Stop-Transcript | Out-Null
    exit 1
}
Write-Ok "React renderer built"

Write-Info "Building Electron main..."
& $nodeExe $npmCli run build:main 2>&1 | Tee-Object -FilePath (Join-Path $SharedRoot "build_step.log") -Append
if ($LASTEXITCODE -ne 0) {
    $tail = Get-Content (Join-Path $SharedRoot "build_step.log") -Tail 40 -ErrorAction SilentlyContinue
    "FAILED: Electron main build failed`n--- last 40 lines ---`n$($tail -join "`n")" | Out-File -FilePath (Join-Path $SharedRoot "vm_build_status.txt") -Force -Encoding ascii
    Stop-Transcript | Out-Null
    exit 1
}
Write-Ok "Electron main built"

# Step 6: Build Python Sidecar
Write-Step "Step 6/8: Build Python Sidecar (PyInstaller)"

$sidecarDir = Join-Path $LocalRoot "sidecar"
$sidecarDist = Join-Path $sidecarDir "dist"

if (Test-Path $sidecarDist) {
    Remove-Item -Recurse -Force $sidecarDist -ErrorAction SilentlyContinue
}

Write-Info "Running PyInstaller (may take 1-2 minutes)..."

# V5 模块列表（需要打包进 sidecar）
$v5Modules = @(
    "image_slicer.py", "image_safety.py", "hotspot_slicer.py",
    "html_assembler.py", "clipboard_html.py", "outlook_sender.py",
    "pdf_slicer.py", "ppt_slicer.py", "psd_slicer.py", "clickable_map.py"
)

$pyiArgs = @(
    "--onefile", "--name", "sidecar_server",
    "--distpath", $sidecarDist,
    "--workpath", (Join-Path $sidecarDir "build"),
    "--specpath", $sidecarDir,
    "--noconfirm", "--clean",
    "--collect-all", "PIL", "--collect-all", "fitz", "--collect-all", "win32com",
    "--hidden-import", "pythoncom", "--hidden-import", "win32com.client"
)

# 添加 V5 模块作为数据文件
foreach ($mod in $v5Modules) {
    $srcPath = Join-Path $LocalRoot $mod
    if (Test-Path $srcPath) {
        $pyiArgs += @("--add-data", "$srcPath;.")
    }
}

$pyiArgs += (Join-Path $sidecarDir "sidecar_server.py")

& $pythonExe -m PyInstaller @pyiArgs 2>&1 | Out-Null

$sidecarExe = Join-Path $sidecarDist "sidecar_server.exe"
if (-not (Test-Path $sidecarExe)) {
    Fail "Sidecar build failed - sidecar_server.exe not generated"
}

$sidecarSizeMB = [math]::Round((Get-Item $sidecarExe).Length / 1MB, 1)
Write-Ok "Sidecar built ($sidecarSizeMB MB)"

# Step 7: Build Electron Portable EXE
Write-Step "Step 7/8: Build Electron Portable EXE"

Write-Info "Running electron-builder (may take 3-5 minutes)..."

& $nodeExe $npmCli run dist:win 2>&1 | Tee-Object -FilePath (Join-Path $SharedRoot "build_step.log") -Append
if ($LASTEXITCODE -ne 0) {
    $tail = Get-Content (Join-Path $SharedRoot "build_step.log") -Tail 40 -ErrorAction SilentlyContinue
    "FAILED: Electron build failed`n--- last 40 lines of build_step.log ---`n$($tail -join "`n")" | Out-File -FilePath (Join-Path $SharedRoot "vm_build_status.txt") -Force -Encoding ascii
    Stop-Transcript | Out-Null
    exit 1
}

# Verify output
$outDir = Join-Path $LocalRoot "dist"
if (-not (Test-Path $outDir)) {
    Fail "Output directory dist/ not found"
}

$exeFiles = Get-ChildItem -Path $outDir -Filter "*.exe"
if (-not $exeFiles -or $exeFiles.Count -eq 0) {
    Fail "No EXE file found in dist/"
}

$resultExe = $exeFiles | Where-Object { $_.Name -like "*portable*" } | Select-Object -First 1
if (-not $resultExe) { $resultExe = $exeFiles | Select-Object -First 1 }

# Cleanup: keep only portable EXE
Write-Info "Cleaning build artifacts, keep only portable EXE..."
$keepName = $resultExe.Name
Get-ChildItem -Path $outDir | Where-Object { $_.Name -ne $keepName } | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}
Write-Ok "Cleaned, kept only: $keepName"

$finalSizeMB = [math]::Round((Get-Item $resultExe).Length / 1MB, 1)

# Step 8: Copy result back to shared folder
Write-Step "Step 8/8: Copy result to shared folder"

$sharedDist = Join-Path $SharedRoot "dist"
if (-not (Test-Path $sharedDist)) {
    New-Item -ItemType Directory -Path $sharedDist -Force | Out-Null
}

# Clean shared dist
Get-ChildItem -Path $sharedDist -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
}

# Copy EXE
Copy-Item -Path $resultExe.FullName -Destination $sharedDist -Force
Write-Ok "EXE copied to $sharedDist"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  File: $($resultExe.Name)" -ForegroundColor Green
Write-Host "  Size: $finalSizeMB MB" -ForegroundColor Green
Write-Host "  Local: $($resultExe.FullName)" -ForegroundColor Green
Write-Host "  Shared: $sharedDist\$($resultExe.Name)" -ForegroundColor Green
Write-Host ""

"SUCCESS: $($resultExe.Name) ($finalSizeMB MB)" | Out-File -FilePath "\\Mac\Home\Documents\outlook-img-slicer\vm_build_status.txt" -Force -Encoding ascii
Stop-Transcript | Out-Null
exit 0
