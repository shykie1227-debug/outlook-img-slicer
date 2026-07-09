<#
.SYNOPSIS
Wrapper to launch vm_build.ps1 as an independent detached process

.DESCRIPTION
prlctl exec disconnects on long-running commands. This wrapper starts
vm_build.ps1 as a detached process so the build continues even if
prlctl exec disconnects.
#>

$buildScript = "\\Mac\Home\outlook-img-slicer\vm_build.ps1"
$logFile = "\\Mac\Home\outlook-img-slicer\vm_build.log"
$statusFile = "\\Mac\Home\outlook-img-slicer\vm_build_status.txt"

# Write status marker
"RUNNING" | Out-File -FilePath $statusFile -Force -Encoding ascii

# Launch build script as detached process
$proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File",$buildScript `
    -WindowStyle Hidden `
    -PassThru

$proc.Id | Out-File -FilePath "\\Mac\Home\outlook-img-slicer\vm_build_pid.txt" -Force -Encoding ascii

Write-Host "Build launched as PID $($proc.Id)"
Write-Host "Monitor: $logFile"
