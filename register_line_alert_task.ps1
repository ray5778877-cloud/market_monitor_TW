#Requires -Version 5.1
<#
.SYNOPSIS
  Register weekday 08:30 LINE alert task (current user, no admin).

.USAGE
  cd <project>\market_monitor_TW
  Set-ExecutionPolicy -Scope Process Bypass -Force
  .\register_line_alert_task.ps1
#>

$TaskName = "MarketMonitorTW_LineAlert_0830"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $Root "run_line_alert.bat"

if (-not (Test-Path -LiteralPath $BatPath)) {
    Write-Host "ERROR: bat not found: $BatPath" -ForegroundColor Red
    exit 1
}

# Remove old tasks quietly (ignore "not found")
$oldNames = @("MarketMonitorTW_LineAlert_1315", "MarketMonitorTW_LineAlert_0830")
foreach ($name in $oldNames) {
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($null -ne $existing) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "Removed old task: $name"
    }
}

# Create with schtasks (current user, no UserId param issues)
# /TR must be quoted path to bat
$tr = "`"$BatPath`""
$args = @(
    "/Create",
    "/TN", $TaskName,
    "/TR", $tr,
    "/SC", "WEEKLY",
    "/D", "MON,TUE,WED,THU,FRI",
    "/ST", "08:30",
    "/F"
)

Write-Host "Creating task with schtasks..."
& schtasks.exe @args
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: schtasks create failed (exit $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Try: right-click PowerShell -> Run as administrator, then rerun this script."
    exit 1
}

# Verify
$query = & schtasks.exe /Query /TN $TaskName /FO LIST
Write-Host $query
Write-Host ""
Write-Host "OK: Scheduled task registered: $TaskName" -ForegroundColor Green
Write-Host "  When : Mon-Fri 08:30"
Write-Host "  What : backtest_2.py -> line_alert.py"
Write-Host "  Bat  : $BatPath"
Write-Host ""
Write-Host "Test : Start-ScheduledTask -TaskName $TaskName"
Write-Host "   or: schtasks /Run /TN $TaskName"
Write-Host ""
