<#
.SYNOPSIS
Outlook 长图助手 V6 - 一键打包脚本

.DESCRIPTION
全自动打包脚本，无需任何参数输入，双击即可完成全部打包流程。
功能：
  1. 自动检测运行环境
  2. 自动备份关键配置文件
  3. 自动识别并清理冗余打包脚本
  4. 自动配置国内镜像（首次运行）
  5. 自动安装依赖
  6. 自动执行完整构建流程
  7. 自动验证构建结果
  8. 生成清理日志报告

.NOTES
文件名: 一键打包.ps1
版本: 1.0.0
配合: 一键打包.bat（双击启动）
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$script:ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$script:LogFile = Join-Path $script:ProjectRoot "打包日志_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
$script:CleanupLog = @()
$script:BackupDir = $null
$script:TotalSteps = 8
$script:CurrentStep = 0

function Write-Log {
    param(
        [string]$Message,
        [string]$Level = "INFO"
    )
    $timestamp = Get-Date -Format "HH:mm:ss"
    $logLine = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:LogFile -Value $logLine -Encoding UTF8
}

function Write-Step {
    param([string]$Title)
    $script:CurrentStep++
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║  步骤 $script:CurrentStep / $script:TotalSteps : $Title" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Log "=== 步骤 $script:CurrentStep : $Title ==="
}

function Write-Ok {
    param([string]$Message)
    Write-Host "  [OK] " -ForegroundColor Green -NoNewline
    Write-Host $Message
    Write-Log $Message "OK"
}

function Write-Err {
    param([string]$Message)
    Write-Host "  [错误] " -ForegroundColor Red -NoNewline
    Write-Host $Message
    Write-Log $Message "ERROR"
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [警告] " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
    Write-Log $Message "WARN"
}

function Write-Info {
    param([string]$Message)
    Write-Host "  [信息] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
    Write-Log $Message "INFO"
}

function Stop-WithError {
    param([string]$Message)
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Red
    Write-Host "║  ❌ 打包失败" -ForegroundColor Red
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Red
    Write-Err $Message
    Write-Host ""
    Write-Host "  日志文件: $script:LogFile" -ForegroundColor Yellow
    Write-Host ""
    Write-Log "打包失败: $Message" "ERROR"
    exit 1
}

function Test-CommandExists {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

function Find-NodeJs {
    $commonPaths = @(
        "$env:ProgramFiles\nodejs\node.exe",
        "${env:ProgramFiles(x86)}\nodejs\node.exe",
        "$env:LOCALAPPDATA\Programs\nodejs\node.exe"
    )
    foreach ($path in $commonPaths) {
        if (Test-Path $path) { return $path }
    }
    $nodeInPath = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeInPath) { return $nodeInPath.Source }
    return $null
}

function Find-Python {
    $pythonInPath = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonInPath) { return $pythonInPath.Source }
    $pyInPath = Get-Command py -ErrorAction SilentlyContinue
    if ($pyInPath) { return $pyInPath.Source }
    $versions = @("314", "313", "312", "311", "310")
    foreach ($v in $versions) {
        $path = "$env:LOCALAPPDATA\Programs\Python\Python$v\python.exe"
        if (Test-Path $path) { return $path }
    }
    return $null
}

function Backup-ConfigFiles {
    Write-Step "备份关键配置文件"

    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $script:BackupDir = Join-Path $script:ProjectRoot "backup_$timestamp"
    $null = New-Item -ItemType Directory -Path $script:BackupDir -Force

    $filesToBackup = @(
        "package.json",
        "electron-builder.yml",
        "app/package.json",
        "electron/package.json",
        "requirements.txt"
    )

    $backedUp = 0
    foreach ($file in $filesToBackup) {
        $src = Join-Path $script:ProjectRoot $file
        if (Test-Path $src) {
            $destDir = Join-Path $script:BackupDir (Split-Path -Parent $file)
            if (-not (Test-Path $destDir)) {
                $null = New-Item -ItemType Directory -Path $destDir -Force
            }
            Copy-Item -Path $src -Destination (Join-Path $script:BackupDir $file) -Force
            Write-Ok "已备份: $file"
            $backedUp++
        }
    }

    Write-Info "备份目录: $script:BackupDir"
    Write-Info "共备份 $backedUp 个文件"
    Write-Log "备份完成，共 $backedUp 个文件，目录: $script:BackupDir"
}

function Invoke-Cleanup {
    Write-Step "清理冗余打包脚本和文件"

    $redundantPatterns = @(
        "build_v5*.py",
        "build_v5*.ps1",
        "build_v5*.bat",
        "package-v5*.ps1",
        "package-v5*.bat",
        "*.spec",
        "__pycache__",
        ".pytest_cache"
    )

    $removedCount = 0
    $removedItems = @()

    foreach ($pattern in $redundantPatterns) {
        $items = Get-ChildItem -Path $script:ProjectRoot -Filter $pattern -Recurse -ErrorAction SilentlyContinue |
                 Where-Object { $_.FullName -notlike "*\legacy\*" -and $_.FullName -notlike "*\node_modules\*" -and $_.FullName -notlike "*\backup_*\*" }

        foreach ($item in $items) {
            try {
                if ($item.PSIsContainer) {
                    Remove-Item -Path $item.FullName -Recurse -Force -ErrorAction Stop
                } else {
                    Remove-Item -Path $item.FullName -Force -ErrorAction Stop
                }
                $relativePath = $item.FullName.Replace($script:ProjectRoot + "\", "")
                $script:CleanupLog += "已删除: $relativePath"
                Write-Ok "已删除: $relativePath"
                $removedCount++
            }
            catch {
                $script:CleanupLog += "跳过: $($item.Name) - $($_.Exception.Message)"
                Write-Warn "跳过: $($item.Name)"
            }
        }
    }

    $distDirs = @("app\dist", "electron\dist-electron", "sidecar\dist", "sidecar\build", "release-artifacts\electron")
    foreach ($dir in $distDirs) {
        $fullPath = Join-Path $script:ProjectRoot $dir
        if (Test-Path $fullPath) {
            try {
                Remove-Item -Path $fullPath -Recurse -Force -ErrorAction Stop
                $script:CleanupLog += "已清理构建缓存: $dir"
                Write-Ok "已清理: $dir"
                $removedCount++
            }
            catch {
                $script:CleanupLog += "跳过清理: $dir - $($_.Exception.Message)"
            }
        }
    }

    Write-Info "共清理 $removedCount 项"
    Write-Log "清理完成，共 $removedCount 项"
}

function Invoke-EnvironmentCheck {
    Write-Step "检测构建环境"

    $nodePath = Find-NodeJs
    if (-not $nodePath) {
        Stop-WithError "未找到 Node.js，请先从 https://nodejs.org/ 下载安装 Node.js 18+"
    }
    $nodeVersion = & $nodePath --version
    Write-Ok "Node.js: $nodeVersion"

    $nodeDir = Split-Path -Parent $nodePath
    if (-not ($env:PATH -like "*$nodeDir*")) {
        $env:PATH = "$nodeDir;$env:PATH"
    }

    $npmCli = Join-Path $nodeDir "node_modules\npm\bin\npm-cli.js"
    if (-not (Test-Path $npmCli)) {
        Stop-WithError "未找到 npm，请检查 Node.js 安装是否完整"
    }
    $npmVersion = & $nodePath $npmCli --version
    Write-Ok "npm: $npmVersion"

    $pythonPath = Find-Python
    if (-not $pythonPath) {
        Stop-WithError "未找到 Python，请先从 https://www.python.org/ 下载安装 Python 3.10+"
    }
    $pythonVersion = & $pythonPath --version
    Write-Ok "Python: $pythonVersion"

    Write-Log "环境检测完成: Node.js $nodeVersion, npm $npmVersion, Python $pythonVersion"
    return @{
        NodePath = $nodePath
        NpmCli = $npmCli
        PythonPath = $pythonPath
    }
}

function Invoke-MirrorSetup {
    param($EnvInfo)

    Write-Step "配置国内镜像加速"

    Write-Info "正在设置 npm 镜像..."
    & $EnvInfo.NodePath $EnvInfo.NpmCli config set registry https://registry.npmmirror.com/ 2>&1 | Out-Null

    Write-Info "正在设置 Electron 二进制镜像..."
    & $EnvInfo.NodePath $EnvInfo.NpmCli config set electron_mirror https://npmmirror.com/mirrors/electron/ 2>&1 | Out-Null

    Write-Info "正在设置 electron-builder 二进制镜像..."
    & $EnvInfo.NodePath $EnvInfo.NpmCli config set electron-builder-binaries_mirror https://npmmirror.com/mirrors/electron-builder-binaries/ 2>&1 | Out-Null

    $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
    $env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

    Write-Ok "国内镜像配置完成"
    Write-Log "国内镜像配置完成"
}

function Invoke-NpmInstall {
    param($EnvInfo)

    Write-Step "安装 Node.js 依赖"

    $nodeModules = Join-Path $script:ProjectRoot "node_modules"
    if (Test-Path $nodeModules) {
        Write-Info "检测到已有 node_modules，跳过安装"
        Write-Log "跳过 npm install（node_modules 已存在）"
        return
    }

    Write-Info "正在安装依赖（首次运行可能需要 3-5 分钟）..."
    $result = & $EnvInfo.NodePath $EnvInfo.NpmCli install 2>&1

    if ($LASTEXITCODE -ne 0) {
        Stop-WithError "npm install 失败，请检查网络连接或使用国内镜像"
    }

    Write-Ok "Node.js 依赖安装完成"
    Write-Log "npm install 完成"
}

function Invoke-PipInstall {
    param($EnvInfo)

    Write-Step "安装 Python 依赖"

    $reqFile = Join-Path $script:ProjectRoot "requirements.txt"
    if (-not (Test-Path $reqFile)) {
        Write-Warn "requirements.txt 不存在，跳过"
        return
    }

    Write-Info "正在检查并安装 Python 依赖..."
    $result = & $EnvInfo.PythonPath -m pip install -r $reqFile 2>&1

    if ($LASTEXITCODE -ne 0) {
        Write-Warn "部分依赖安装失败，继续尝试构建..."
    }

    Write-Ok "Python 依赖处理完成"
    Write-Log "Python 依赖安装完成"
}

function Invoke-BuildRenderer {
    param($EnvInfo)

    Write-Step "构建 React 渲染进程"

    Write-Info "正在构建渲染进程..."
    Push-Location $script:ProjectRoot
    try {
        $result = & $EnvInfo.NodePath $EnvInfo.NpmCli run build:renderer 2>&1
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "渲染进程构建失败"
        }
    }
    finally {
        Pop-Location
    }

    $indexHtml = Join-Path $script:ProjectRoot "app\dist\index.html"
    if (-not (Test-Path $indexHtml)) {
        Stop-WithError "渲染进程构建失败，未找到 index.html"
    }

    Write-Ok "渲染进程构建完成"
    Write-Log "渲染进程构建完成"
}

function Invoke-BuildMain {
    param($EnvInfo)

    Write-Step "构建 Electron 主进程"

    Write-Info "正在构建主进程..."
    Push-Location $script:ProjectRoot
    try {
        $result = & $EnvInfo.NodePath $EnvInfo.NpmCli run build:main 2>&1
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "主进程构建失败"
        }
    }
    finally {
        Pop-Location
    }

    $mainJs = Join-Path $script:ProjectRoot "electron\dist-electron\main.js"
    if (-not (Test-Path $mainJs)) {
        Stop-WithError "主进程构建失败，未找到 main.js"
    }

    Write-Ok "主进程构建完成"
    Write-Log "主进程构建完成"
}

function Invoke-BuildSidecar {
    param($EnvInfo)

    Write-Step "打包 Python Sidecar"

    Write-Info "正在使用 PyInstaller 打包 Sidecar（可能需要 1-2 分钟）..."

    $sidecarDir = Join-Path $script:ProjectRoot "sidecar"
    $distDir = Join-Path $sidecarDir "dist"

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

    Push-Location $script:ProjectRoot
    try {
        & $EnvInfo.PythonPath -m PyInstaller --onefile --name sidecar_server `
            --distpath $distDir --workpath "$sidecarDir\build" --specpath $sidecarDir `
            --noconfirm --clean --collect-all PIL --collect-all fitz --collect-all win32com `
            "$sidecarDir\sidecar_server.py" 2>&1 | Out-Null

        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "Sidecar 打包失败"
        }
    }
    finally {
        Pop-Location
    }

    $stopwatch.Stop()

    $exePath = Join-Path $distDir "sidecar_server.exe"
    if (-not (Test-Path $exePath)) {
        Stop-WithError "Sidecar 打包失败，未找到 sidecar_server.exe"
    }

    $sizeMB = (Get-Item $exePath).Length / 1MB
    Write-Ok "Sidecar 打包完成 ($($sizeMB.ToString('F1')) MB, 耗时 $($stopwatch.Elapsed.Seconds)s)"
    Write-Log "Sidecar 打包完成: $($sizeMB.ToString('F1')) MB, 耗时 $($stopwatch.Elapsed.Seconds)s"
}

function Invoke-BuildElectron {
    param($EnvInfo)

    Write-Step "打包 Windows 绿色免安装版"

    Write-Info "正在使用 electron-builder 打包（首次运行可能需要 3-5 分钟下载资源）..."

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

    Push-Location $script:ProjectRoot
    try {
        & $EnvInfo.NodePath $EnvInfo.NpmCli run dist:win 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Stop-WithError "electron-builder 打包失败"
        }
    }
    finally {
        Pop-Location
    }

    $stopwatch.Stop()
    Write-Info "打包完成，耗时 $($stopwatch.Elapsed.Seconds)s"
    Write-Log "Electron 打包完成，耗时 $($stopwatch.Elapsed.Seconds)s"
}

function Invoke-VerifyBuild {
    Write-Step "验证构建结果"

    $artifactDir = Join-Path $script:ProjectRoot "release-artifacts\electron"
    if (-not (Test-Path $artifactDir)) {
        Stop-WithError "构建产物目录不存在"
    }

    $exeFiles = Get-ChildItem -Path $artifactDir -Filter "*.exe" -ErrorAction SilentlyContinue
    if (-not $exeFiles -or $exeFiles.Count -eq 0) {
        Stop-WithError "未找到任何 .exe 构建产物"
    }

    $targetExe = $exeFiles | Where-Object { $_.Name -like "*portable*" } | Select-Object -First 1
    if (-not $targetExe) {
        $targetExe = $exeFiles | Select-Object -First 1
    }

    $sizeMB = $targetExe.Length / 1MB

    Write-Ok "文件名: $($targetExe.Name)"
    Write-Ok "文件大小: $($sizeMB.ToString('F1')) MB"
    Write-Ok "保存路径: $($targetExe.FullName)"

    $allFiles = Get-ChildItem -Path $artifactDir
    Write-Info "其他产物: $(($allFiles | ForEach-Object { $_.Name }) -join ', ')"

    Write-Log "构建验证通过: $($targetExe.Name) ($($sizeMB.ToString('F1')) MB)"
    return $targetExe
}

function New-CleanupReport {
    param($ResultExe)

    Write-Step "生成清理日志报告"

    $reportPath = Join-Path $script:ProjectRoot "打包清理报告_$(Get-Date -Format 'yyyyMMdd_HHmmss').md"

    $report = @"
# Outlook 长图助手 V6 打包清理报告

## 基本信息

- **打包时间**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
- **项目目录**: $script:ProjectRoot
- **日志文件**: $script:LogFile
- **备份目录**: $script:BackupDir

## 构建结果

- **状态**: ✅ 成功
- **输出文件**: $($ResultExe.Name)
- **文件大小**: $($ResultExe.Length / 1MB) MB
- **输出路径**: $($ResultExe.FullName)

## 清理记录

共清理 $($script:CleanupLog.Count) 项：

$($script:CleanupLog | ForEach-Object { "- $_" }) -join "`n"

## 备份文件

关键配置文件已备份到: $script:BackupDir

## 使用说明

1. 双击 `一键打包.bat` 即可开始打包
2. 全程无需手动干预，自动完成所有步骤
3. 打包完成后 EXE 文件位于 `release-artifacts\electron\` 目录
4. 详细日志请查看本目录下的 `打包日志_*.log` 文件

---
*报告由一键打包脚本自动生成*
"@

    Set-Content -Path $reportPath -Value $report -Encoding UTF8
    Write-Ok "清理报告已生成: $(Split-Path $reportPath -Leaf)"
    Write-Log "清理报告生成完成: $reportPath"
}

function Show-Success {
    param($ResultExe)

    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║" -ForegroundColor Green -NoNewline
    Write-Host "  ✅  打包成功！" -ForegroundColor Green -NoNewline
    Write-Host (" " * (48 - 10)) -ForegroundColor Green
    Write-Host "║" -ForegroundColor Green
    Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Green
    Write-Host "║" -ForegroundColor Green -NoNewline
    Write-Host "  文件名: $($ResultExe.Name)" -ForegroundColor White -NoNewline
    $padding = 50 - 8 - $ResultExe.Name.Length
    if ($padding -lt 0) { $padding = 0 }
    Write-Host (" " * $padding) -ForegroundColor Green
    Write-Host "║" -ForegroundColor Green
    Write-Host "║" -ForegroundColor Green -NoNewline
    $sizeStr = "$($ResultExe.Length / 1MB) MB"
    Write-Host "  大小: $sizeStr" -ForegroundColor White -NoNewline
    $padding = 50 - 6 - $sizeStr.Length
    if ($padding -lt 0) { $padding = 0 }
    Write-Host (" " * $padding) -ForegroundColor Green
    Write-Host "║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "  输出目录: release-artifacts\electron\" -ForegroundColor Cyan
    Write-Host "  日志文件: $(Split-Path $script:LogFile -Leaf)" -ForegroundColor Cyan
    Write-Host ""

    Write-Log "打包成功，输出: $($ResultExe.FullName)"
}

$null = New-Item -ItemType File -Path $script:LogFile -Force
Write-Log "=== 一键打包脚本启动 ==="
Write-Log "项目目录: $script:ProjectRoot"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║" -ForegroundColor Cyan -NoNewline
Write-Host "  Outlook 长图助手 V6 - 一键打包" -ForegroundColor Cyan -NoNewline
Write-Host (" " * 22) -ForegroundColor Cyan
Write-Host "║" -ForegroundColor Cyan
Write-Host "║" -ForegroundColor Cyan -NoNewline
Write-Host "  全程自动，无需手动操作" -ForegroundColor Yellow -NoNewline
Write-Host (" " * 28) -ForegroundColor Cyan
Write-Host "║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "  预计总耗时: 5-10 分钟（取决于网络速度）" -ForegroundColor Cyan
Write-Host ""

try {
    Backup-ConfigFiles
    Invoke-Cleanup
    $envInfo = Invoke-EnvironmentCheck
    Invoke-MirrorSetup $envInfo
    Invoke-NpmInstall $envInfo
    Invoke-PipInstall $envInfo
    Invoke-BuildRenderer $envInfo
    Invoke-BuildMain $envInfo
    Invoke-BuildSidecar $envInfo
    Invoke-BuildElectron $envInfo
    $resultExe = Invoke-VerifyBuild
    New-CleanupReport $resultExe
    Show-Success $resultExe
}
catch {
    $errorMsg = $_.Exception.Message
    Stop-WithError $errorMsg
}
