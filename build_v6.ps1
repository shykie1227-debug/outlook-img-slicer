<#
.SYNOPSIS
Outlook 长图助手 V6 一键打包脚本（Windows PowerShell）

.DESCRIPTION
自动检测 Node.js 和 Python 环境，执行完整构建流程。
输出文件: release-artifacts/electron/Outlook 长图助手-V6.0.0-Setup.exe

.REQUIREMENTS
- Node.js 18+ (https://nodejs.org/)
- Python 3.10+ (https://www.python.org/)
- PyInstaller (pip install pyinstaller)

.EXAMPLE
.\build_v6.ps1
#>

param(
    [string]$NodePath = "",
    [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "  Outlook 长图助手 V6 一键打包脚本" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Host "项目目录: $projectRoot"
Write-Host "PowerShell 版本: $($PSVersionTable.PSVersion)"
Write-Host "================================================" -ForegroundColor Cyan

function Find-NodeJs {
    if ($NodePath -and (Test-Path $NodePath)) {
        Write-Host "[OK] 使用指定的 Node.js 路径: $NodePath" -ForegroundColor Green
        return $NodePath
    }

    $commonPaths = @(
        "$env:ProgramFiles\nodejs\node.exe",
        "${env:ProgramFiles(x86)}\nodejs\node.exe",
        "$env:LOCALAPPDATA\Programs\nodejs\node.exe",
        "$env:APPDATA\npm\node_modules\node\bin\node.exe"
    )

    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            Write-Host "[OK] 找到 Node.js: $path" -ForegroundColor Green
            return $path
        }
    }

    $nodeInPath = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeInPath) {
        Write-Host "[OK] 在 PATH 中找到 Node.js: $($nodeInPath.Source)" -ForegroundColor Green
        return $nodeInPath.Source
    }

    Write-Host "[ERROR] 未找到 Node.js!" -ForegroundColor Red
    Write-Host "        请从 https://nodejs.org/ 下载安装 Node.js 18+" -ForegroundColor Yellow
    Write-Host "        安装时请勾选 'Add to PATH'" -ForegroundColor Yellow
    return $null
}

function Find-Npm {
    param([string]$NodePath)

    $nodeDir = Split-Path -Parent $NodePath
    $npmPaths = @(
        Join-Path $nodeDir "npm.cmd",
        Join-Path $nodeDir "npm.ps1",
        Join-Path $nodeDir "node_modules\npm\bin\npm-cli.js"
    )

    foreach ($path in $npmPaths) {
        if (Test-Path $path) {
            if ($path.EndsWith(".cmd") -or $path.EndsWith(".ps1")) {
                Write-Host "[OK] 找到 npm: $path" -ForegroundColor Green
                return $path
            }
            elseif ($path.EndsWith("npm-cli.js")) {
                Write-Host "[OK] 找到 npm-cli.js: $path" -ForegroundColor Green
                return "node `"$path`""
            }
        }
    }

    $npmInPath = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmInPath) {
        Write-Host "[OK] 在 PATH 中找到 npm: $($npmInPath.Source)" -ForegroundColor Green
        return "npm"
    }

    Write-Host "[ERROR] 未找到 npm!" -ForegroundColor Red
    return $null
}

function Find-Python {
    if ($PythonPath -and (Test-Path $PythonPath)) {
        Write-Host "[OK] 使用指定的 Python 路径: $PythonPath" -ForegroundColor Green
        return $PythonPath
    }

    $pythonInPath = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonInPath) {
        Write-Host "[OK] 在 PATH 中找到 Python: $($pythonInPath.Source)" -ForegroundColor Green
        return $pythonInPath.Source
    }

    $python3InPath = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3InPath) {
        Write-Host "[OK] 在 PATH 中找到 Python3: $($python3InPath.Source)" -ForegroundColor Green
        return $python3InPath.Source
    }

    $commonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python314\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe"
    )

    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            Write-Host "[OK] 找到 Python: $path" -ForegroundColor Green
            return $path
        }
    }

    Write-Host "[ERROR] 未找到 Python!" -ForegroundColor Red
    Write-Host "        请从 https://www.python.org/ 下载安装 Python 3.10+" -ForegroundColor Yellow
    Write-Host "        安装时请勾选 'Add Python to PATH'" -ForegroundColor Yellow
    return $null
}

function Invoke-NpmCommand {
    param(
        [string]$NpmPath,
        [string]$Command
    )

    Write-Host "`n>>> npm $Command" -ForegroundColor Cyan

    if ($NpmPath -eq "npm") {
        & npm $Command
    }
    elseif ($NpmPath.EndsWith(".cmd")) {
        & $NpmPath $Command
    }
    elseif ($NpmPath.EndsWith(".ps1")) {
        & powershell -ExecutionPolicy Bypass -File $NpmPath $Command
    }
    elseif ($NpmPath -match "npm-cli.js") {
        & node $NpmPath $Command
    }
    else {
        Write-Host "[ERROR] 无法识别的 npm 路径: $NpmPath" -ForegroundColor Red
        exit 1
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] npm 命令执行失败，退出码: $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
}

function Invoke-PythonCommand {
    param(
        [string]$PythonPath,
        [string]$Command
    )

    Write-Host "`n>>> python $Command" -ForegroundColor Cyan
    & $PythonPath $Command

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Python 命令执行失败，退出码: $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }
}

$nodePath = Find-NodeJs
if (-not $nodePath) { exit 1 }

$npmPath = Find-Npm $nodePath
if (-not $npmPath) { exit 1 }

$pythonPath = Find-Python
if (-not $pythonPath) { exit 1 }

$nodeDir = Split-Path -Parent $nodePath
if (-not ($env:PATH -like "*$nodeDir*")) {
    Write-Host "[INFO] 将 Node.js 目录加入 PATH..." -ForegroundColor Yellow
    $env:PATH = "$nodeDir;$env:PATH"
}

Write-Host "`n=== 安装 Node.js 依赖 ===" -ForegroundColor Cyan
Invoke-NpmCommand $npmPath "install"

Write-Host "`n=== 安装 Python 依赖 ===" -ForegroundColor Cyan
$reqFile = Join-Path $projectRoot "requirements.txt"
if (Test-Path $reqFile) {
    Invoke-PythonCommand $pythonPath "-m pip install -r `"$reqFile`""
}
else {
    Write-Host "[WARNING] requirements.txt 不存在，跳过 Python 依赖安装" -ForegroundColor Yellow
}

Write-Host "`n=== 构建 React 渲染进程 ===" -ForegroundColor Cyan
Invoke-NpmCommand $npmPath "run build:renderer"

Write-Host "`n=== 构建 Electron 主进程 ===" -ForegroundColor Cyan
Invoke-NpmCommand $npmPath "run build:main"

Write-Host "`n=== 打包 Python Sidecar ===" -ForegroundColor Cyan
$sidecarDir = Join-Path $projectRoot "sidecar"
$distDir = Join-Path $sidecarDir "dist"
$buildDir = Join-Path $sidecarDir "build"

if (Test-Path $distDir) {
    Write-Host "清理旧的 Sidecar 构建..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $distDir -ErrorAction SilentlyContinue
}

Invoke-PythonCommand $pythonPath "-m PyInstaller --onefile --name sidecar_server --distpath `"$distDir`" --workpath `"$buildDir`" --specpath `"$sidecarDir`" --noconfirm --clean `"$sidecarDir\sidecar_server.py`""

$exePath = Join-Path $distDir "sidecar_server.exe"
if (Test-Path $exePath) {
    $sizeMB = (Get-Item $exePath).Length / 1MB
    Write-Host "[OK] Sidecar 打包成功: $exePath ($($sizeMB.ToString('F1')) MB)" -ForegroundColor Green
}
else {
    Write-Host "[ERROR] Sidecar 打包失败" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== 使用 electron-builder 打包 ===" -ForegroundColor Cyan
Invoke-NpmCommand $npmPath "run dist:win"

Write-Host "`n=== 验证构建结果 ===" -ForegroundColor Cyan
$artifactDir = Join-Path $projectRoot "release-artifacts" "electron"
if (-not (Test-Path $artifactDir)) {
    Write-Host "[ERROR] 构建产物目录不存在: $artifactDir" -ForegroundColor Red
    exit 1
}

$setupExe = Get-ChildItem -Path $artifactDir -Filter "*Setup*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($setupExe) {
    $sizeMB = $setupExe.Length / 1MB
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "✅ 所有构建步骤完成！" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "输出文件: $($setupExe.FullName)" -ForegroundColor Green
    Write-Host "文件大小: $($sizeMB.ToString('F1')) MB" -ForegroundColor Green
}
else {
    Write-Host "[ERROR] 未找到 Setup.exe 文件" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "请按任意键退出..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
