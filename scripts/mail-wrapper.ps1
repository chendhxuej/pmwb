# mail-wrapper.ps1
# NSSM 服务入口：拉起邮件中心 (tsx.cmd)，并阻塞以保持服务存活。
$ErrorActionPreference = 'Stop'

$node    = "C:\Users\chend\.workbuddy\binaries\node\versions\22.22.2\node.exe"
$mailDir = "D:\项目\统一邮件中心\server"

Write-Host "[mail-wrapper] launching mail center on :3210 ..."
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName        = $node
$psi.Arguments       = "node_modules/.bin/tsx.cmd src/index.ts"
$psi.WorkingDirectory = $mailDir
$psi.UseShellExecute = $false
$psi.CreateNoWindow  = $true
$p = [System.Diagnostics.Process]::Start($psi)
$p.WaitForExit()
exit $p.ExitCode
