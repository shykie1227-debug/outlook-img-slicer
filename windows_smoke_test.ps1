param(
    [string]$ExePath = "C:\build\outlook-img-slicer\desktop\dist\OutlookImgSlicer.exe"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $ExePath)) {
    throw "EXE not found: $ExePath"
}

$version = (Get-Item $ExePath).VersionInfo
Write-Output "FILE_VERSION=$($version.FileVersion)"
Write-Output "PRODUCT_VERSION=$($version.ProductVersion)"

$process = Start-Process -FilePath $ExePath -PassThru
Start-Sleep -Seconds 20
$alive = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
if (-not $alive) {
    throw "EXE exited during startup"
}

Write-Output "STARTUP_OK_PID=$($process.Id)"
Stop-Process -Id $process.Id -Force
