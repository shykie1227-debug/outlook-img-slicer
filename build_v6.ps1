<#
.SYNOPSIS
Outlook 长图助手 V6 一键打包脚本（Windows PowerShell）

.DESCRIPTION
自动检测 Node.js 和 Python 环境，执行完整构建流程。
支持国内镜像加速，提供详细错误诊断。

.PARAMETER NodePath
指定 Node.js 可执行文件路径（可选）

.PARAMETER PythonPath
指定 Python 可执行文件路径（可选）

.PARAMETER SkipNpmInstall
跳过 npm install 步骤

.PARAMETER SkipPipInstall
跳过 pip install 步骤

.PARAMETER UseMirror
使用国内镜像加速下载（推荐）

.EXAMPLE
.\build_v6.ps1
# 正常构建

.EXAMPLE
.\build_v6.ps1 -UseMirror
# 使用国内镜像加速

.EXAMPLE
.\build_v6.ps1 -SkipNpmInstall -SkipPipInstall
# 跳过依赖安装，直接构建

.OUTPUTS
release-artifacts/electron/Outlook 长图助手-V6.0.0-portable-x64.exe
#>

param(
    [string]$NodePath = "",
    [string]$PythonPath = "",
    [switch]$SkipNpmInstall = $false,
    [switch]$SkipPipInstall = $false,
    [switch]$UseMirror = $false
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition

function Write-Step {
    param([string]$Title)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK] " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Err {
    param([string]$Message)
    Write-Host "[ERROR] " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

function Stop-WithPause {
    param([string]$Message)
    if ($Message) {
        Write-Err $Message
    }
    Write-Host ""
    Write-Host "按任意键退出..." -ForegroundColor Cyan
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

function Find-NodeJs {
    if ($NodePath -and (Test-Path $NodePath)) {
        Write-Ok "使用指定的 Node.js 路径: $NodePath"
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
            Write-Ok "找到 Node.js: $path"
            return $path
        }
    }

    $nodeInPath = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeInPath) {
        Write-Ok "在 PATH 中找到 Node.js: $($nodeInPath.Source)"
        return $nodeInPath.Source
    }

    Write-Err "未找到 Node.js!"
    Write-Host "        请从 https://nodejs.org/ 下载安装 Node.js 18+" -ForegroundColor Yellow
    Write-Host "        安装时请勾选 'Add to PATH'" -ForegroundColor Yellow
    return $null
}

function Get-NpmRunner {
    param([string]$NodePath)

    $nodeDir = Split-Path -Parent $NodePath

    $npmCli = Join-Path $nodeDir "node_modules\npm\bin\npm-cli.js"
    if (Test-Path $npmCli) {
        $version = & $NodePath $npmCli --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "npm: $version (via node + npm-cli.js)"
            return @{
                Type = "NodeCli"
                NodePath = $NodePath
                NpmCli = $npmCli
            }
        }
    }

    $npmCmd = Join-Path $nodeDir "npm.cmd"
    if (Test-Path $npmCmd) {
        $version = & $npmCmd --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "npm: $version ($npmCmd)"
            return @{
                Type = "Direct"
                Path = $npmCmd
            }
        }
    }

    $npmInPath = Get-Command npm -ErrorAction SilentlyContinue
    if ($npmInPath) {
        $version = & npm --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "npm: $version ($($npmInPath.Source))"
            return @{
                Type = "Direct"
                Path = "npm"
            }
        }
    }

    Write-Err "未找到 npm!"
    Write-Info "尝试重新安装 Node.js，并确保勾选 'Add to PATH'"
    return $null
}

function Invoke-Npm {
    param(
        [hashtable]$NpmRunner,
        [string]$Command,
        [string]$WorkingDirectory = $projectRoot
    )

    Write-Info "npm $Command"

    $originalLocation = Get-Location
    try {
        Set-Location $WorkingDirectory

        if ($NpmRunner.Type -eq "NodeCli") {
            & $NpmRunner.NodePath $NpmRunner.NpmCli $Command
        }
        elseif ($NpmRunner.Type -eq "Direct") {
            if ($NpmRunner.Path -eq "npm") {
                & npm $Command
            }
            else {
                & $NpmRunner.Path $Command
            }
        }
        else {
            Write-Err "未知的 npm 运行器类型: $($NpmRunner.Type)"
            Stop-WithPause "无法执行 npm 命令"
        }
    }
    finally {
        Set-Location $originalLocation
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Err "npm 命令执行失败，退出码: $LASTEXITCODE"
        Write-Err "命令: npm $Command"
        Write-Host ""
        Write-Host "常见问题排查：" -ForegroundColor Yellow
        Write-Host "  1. 网络问题：使用 -UseMirror 参数启用国内镜像" -ForegroundColor Yellow
        Write-Host "  2. 权限问题：以管理员身份运行 PowerShell" -ForegroundColor Yellow
        Write-Host "  3. 依赖冲突：删除 node_modules 后重试" -ForegroundColor Yellow
        Stop-WithPause "构建失败，请检查上方错误信息"
    }
}

function Find-Python {
    if ($PythonPath -and (Test-Path $PythonPath)) {
        Write-Ok "使用指定的 Python 路径: $PythonPath"
        return $PythonPath
    }

    $pythonInPath = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonInPath) {
        Write-Ok "在 PATH 中找到 Python: $($pythonInPath.Source)"
        return $pythonInPath.Source
    }

    $python3InPath = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3InPath) {
        Write-Ok "在 PATH 中找到 Python3: $($python3InPath.Source)"
        return $python3InPath.Source
    }

    $pyInPath = Get-Command py -ErrorAction SilentlyContinue
    if ($pyInPath) {
        Write-Ok "在 PATH 中找到 Python Launcher: $($pyInPath.Source)"
        return $pyInPath.Source
    }

    $commonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:ProgramFiles\Python314\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "$env:ProgramFiles\Python310\python.exe"
    )

    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            Write-Ok "找到 Python: $path"
            return $path
        }
    }

    Write-Err "未找到 Python!"
    Write-Host "        请从 https://www.python.org/ 下载安装 Python 3.10+" -ForegroundColor Yellow
    Write-Host "        安装时请勾选 'Add Python to PATH'" -ForegroundColor Yellow
    return $null
}

function Invoke-Python {
    param(
        [string]$PythonPath,
        [string[]]$Arguments,
        [string]$WorkingDirectory = $projectRoot
    )

    $argStr = $Arguments -join ' '
    Write-Info "python $argStr"

    $originalLocation = Get-Location
    try {
        Set-Location $WorkingDirectory
        & $PythonPath $Arguments
    }
    finally {
        Set-Location $originalLocation
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Err "Python 命令执行失败，退出码: $LASTEXITCODE"
        Write-Err "命令: python $argStr"
        Stop-WithPause "构建失败，请检查上方错误信息"
    }
}

function Test-ProjectFiles {
    Write-Step "检查项目文件"

    $requiredFiles = @(
        "package.json",
        "electron-builder.yml",
        "app/package.json",
        "electron/package.json",
        "sidecar/sidecar_server.py",
        "requirements.txt",
        "icon.ico"
    )

    $allOk = $true
    foreach ($file in $requiredFiles) {
        $fullPath = Join-Path $projectRoot $file
        if (Test-Path $fullPath) {
            Write-Ok "存在: $file"
        }
        else {
            Write-Err "缺失: $file"
            $allOk = $false
        }
    }

    if (-not $allOk) {
        Stop-WithPause "项目文件不完整，请检查项目目录"
    }

    return $true
}

function Set-MirrorConfig {
    param([hashtable]$NpmRunner)

    Write-Step "配置国内镜像加速"

    Write-Info "设置 npm 镜像为 npmmirror.com..."
    Invoke-Npm $NpmRunner "config set registry https://registry.npmmirror.com/"

    Write-Info "设置 Electron 二进制下载镜像..."
    Invoke-Npm $NpmRunner "config set electron_mirror https://npmmirror.com/mirrors/electron/"

    Write-Info "设置 electron-builder 二进制下载镜像..."
    Invoke-Npm $NpmRunner "config set electron-builder-binaries_mirror https://npmmirror.com/mirrors/electron-builder-binaries/"

    $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
    $env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

    Write-Ok "国内镜像配置完成"
}

function Install-NodeDependencies {
    param([hashtable]$NpmRunner)

    Write-Step "安装 Node.js 依赖"

    $nodeModules = Join-Path $projectRoot "node_modules"
    if (Test-Path $nodeModules) {
        Write-Info "node_modules 已存在，如需重新安装请先删除该目录"
    }

    Invoke-Npm $NpmRunner "install"
    Write-Ok "Node.js 依赖安装完成"
}

function Install-PythonDependencies {
    param([string]$PythonPath)

    Write-Step "安装 Python 依赖"

    $reqFile = Join-Path $projectRoot "requirements.txt"
    if (-not (Test-Path $reqFile)) {
        Write-Warn "requirements.txt 不存在，跳过 Python 依赖安装"
        return
    }

    Invoke-Python $PythonPath @("-m", "pip", "install", "-r", "`"$reqFile`"")
    Write-Ok "Python 依赖安装完成"
}

function Build-Renderer {
    param([hashtable]$NpmRunner)

    Write-Step "构建 React 渲染进程"

    $distDir = Join-Path $projectRoot "app\dist"
    if (Test-Path $distDir) {
        Write-Info "清理旧的构建产物..."
        Remove-Item -Recurse -Force $distDir -ErrorAction SilentlyContinue
    }

    Invoke-Npm $NpmRunner "run build:renderer"

    $indexHtml = Join-Path $distDir "index.html"
    if (Test-Path $indexHtml) {
        Write-Ok "渲染进程构建完成"
        return $true
    }
    else {
        Write-Err "渲染进程构建失败，未找到 index.html"
        return $false
    }
}

function Build-Main {
    param([hashtable]$NpmRunner)

    Write-Step "构建 Electron 主进程"

    $distDir = Join-Path $projectRoot "electron\dist-electron"
    if (Test-Path $distDir) {
        Write-Info "清理旧的构建产物..."
        Remove-Item -Recurse -Force $distDir -ErrorAction SilentlyContinue
    }

    Invoke-Npm $NpmRunner "run build:main"

    $mainJs = Join-Path $distDir "main.js"
    if (Test-Path $mainJs) {
        Write-Ok "主进程构建完成"
        return $true
    }
    else {
        Write-Err "主进程构建失败，未找到 main.js"
        return $false
    }
}

function Build-Sidecar {
    param([string]$PythonPath)

    Write-Step "打包 Python Sidecar"

    $sidecarDir = Join-Path $projectRoot "sidecar"
    $distDir = Join-Path $sidecarDir "dist"
    $buildDir = Join-Path $sidecarDir "build"
    $specFile = Join-Path $sidecarDir "sidecar_server.spec"

    if (Test-Path $distDir) {
        Write-Info "清理旧的 Sidecar 构建..."
        Remove-Item -Recurse -Force $distDir -ErrorAction SilentlyContinue
    }
    if (Test-Path $buildDir) {
        Remove-Item -Recurse -Force $buildDir -ErrorAction SilentlyContinue
    }
    if (Test-Path $specFile) {
        Remove-Item -Force $specFile -ErrorAction SilentlyContinue
    }

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

    Invoke-Python $PythonPath @(
        "-m", "PyInstaller",
        "--onefile",
        "--name", "sidecar_server",
        "--distpath", "`"$distDir`"",
        "--workpath", "`"$buildDir`"",
        "--specpath", "`"$sidecarDir`"",
        "--noconfirm",
        "--clean",
        "--collect-all", "PIL",
        "--collect-all", "fitz",
        "--collect-all", "win32com",
        "`"$sidecarDir\sidecar_server.py`""
    )

    $stopwatch.Stop()

    $exePath = Join-Path $distDir "sidecar_server.exe"
    if (Test-Path $exePath) {
        $sizeMB = (Get-Item $exePath).Length / 1MB
        Write-Ok "Sidecar 打包成功: $exePath ($($sizeMB.ToString('F1')) MB, 耗时 $($stopwatch.Elapsed.Seconds)s)"
        return $true
    }
    else {
        Write-Err "Sidecar 打包失败，未找到 sidecar_server.exe"
        return $false
    }
}

function Build-Electron {
    param([hashtable]$NpmRunner)

    Write-Step "使用 electron-builder 打包（绿色免安装版）"

    $outputDir = Join-Path $projectRoot "release-artifacts\electron"
    if (Test-Path $outputDir) {
        Write-Info "清理旧的构建产物..."
        Remove-Item -Recurse -Force $outputDir -ErrorAction SilentlyContinue
    }

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

    Invoke-Npm $NpmRunner "run dist:win"

    $stopwatch.Stop()
    Write-Info "electron-builder 完成，耗时 $($stopwatch.Elapsed.Seconds)s"
}

function Test-BuildResult {
    Write-Step "验证构建结果"

    $artifactDir = Join-Path $projectRoot "release-artifacts\electron"
    if (-not (Test-Path $artifactDir)) {
        Write-Err "构建产物目录不存在: $artifactDir"
        return $null
    }

    $exeFiles = Get-ChildItem -Path $artifactDir -Filter "*.exe" -ErrorAction SilentlyContinue
    if (-not $exeFiles -or $exeFiles.Count -eq 0) {
        Write-Err "未找到任何 .exe 文件"
        return $null
    }

    $portableExe = $null
    $setupExe = $null
    foreach ($f in $exeFiles) {
        if ($f.Name -like "*portable*") {
            $portableExe = $f
        }
        elseif ($f.Name -like "*Setup*" -or $f.Name -like "*setup*") {
            $setupExe = $f
        }
    }

    $targetExe = $null
    if ($portableExe) {
        $targetExe = $portableExe
    }
    elseif ($setupExe) {
        $targetExe = $setupExe
    }
    else {
        $targetExe = $exeFiles[0]
    }

    $sizeMB = $targetExe.Length / 1MB
    Write-Ok "找到构建产物: $($targetExe.Name)"
    Write-Ok "文件大小: $($sizeMB.ToString('F1')) MB"
    Write-Ok "完整路径: $($targetExe.FullName)"

    $otherFiles = Get-ChildItem -Path $artifactDir | Where-Object { $_.Name -ne $targetExe.Name }
    if ($otherFiles -and $otherFiles.Count -gt 0) {
        $otherNames = $otherFiles | ForEach-Object { $_.Name }
        Write-Info "其他产物: $($otherNames -join ', ')"
    }

    return $targetExe
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Outlook 长图助手 V6 一键打包脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "项目目录: $projectRoot"
Write-Host "PowerShell 版本: $($PSVersionTable.PSVersion)"
if ($UseMirror) {
    Write-Host "模式: 国内镜像加速" -ForegroundColor Yellow
}
Write-Host "============================================================" -ForegroundColor Cyan

try {
    if (-not (Test-ProjectFiles)) {
        Stop-WithPause ""
    }

    $nodePath = Find-NodeJs
    if (-not $nodePath) { Stop-WithPause "" }

    $npmRunner = Get-NpmRunner $nodePath
    if (-not $npmRunner) { Stop-WithPause "" }

    $pythonPath = Find-Python
    if (-not $pythonPath) { Stop-WithPause "" }

    $nodeDir = Split-Path -Parent $nodePath
    if (-not ($env:PATH -like "*$nodeDir*")) {
        Write-Info "将 Node.js 目录加入 PATH..."
        $env:PATH = "$nodeDir;$env:PATH"
    }

    if ($UseMirror) {
        Set-MirrorConfig $npmRunner
    }

    if (-not $SkipNpmInstall) {
        Install-NodeDependencies $npmRunner
    }
    else {
        Write-Info "跳过 npm install（-SkipNpmInstall）"
    }

    if (-not $SkipPipInstall) {
        Install-PythonDependencies $pythonPath
    }
    else {
        Write-Info "跳过 pip install（-SkipPipInstall）"
    }

    if (-not (Build-Renderer $npmRunner)) {
        Stop-WithPause ""
    }

    if (-not (Build-Main $npmRunner)) {
        Stop-WithPause ""
    }

    if (-not (Build-Sidecar $pythonPath)) {
        Stop-WithPause ""
    }

    Build-Electron $npmRunner

    $resultExe = Test-BuildResult
    if ($resultExe) {
        Write-Host ""
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "  ✅ 所有构建步骤完成！" -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "输出文件: $($resultExe.FullName)" -ForegroundColor Green
        Write-Host "文件大小: $((Get-Item $resultExe).Length / 1MB).ToString('F1') MB" -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
    }
    else {
        Stop-WithPause "构建验证失败"
    }
}
catch {
    Write-Err "构建脚本发生未预期的错误: $($_.Exception.Message)"
    Write-Host $_.ScriptStackTrace -ForegroundColor Gray
    Stop-WithPause ""
}

Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
