<#
.SYNOPSIS
Run Game Bub as a virtual Xbox controller; Ctrl+C releases buttons and disconnects.
#>
param(
    [string]$Receiver = '192.168.0.157',
    [string]$BindAddress = '192.168.0.47',
    [ValidateRange(1,7200)][int]$Seconds = 7200,
    [switch]$ObserveOnly,
    [ValidateSet('standard','elden-ring','mass-effect','wow')][string]$Profile = 'standard'
)
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = "Game Bub Xbox Controller - $Profile (Ctrl+C to disconnect)"
$controllerPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $controllerPython)) {
    throw 'Prepare the lab environment first: py -3.11 -m uv sync --locked'
}
$controllerArgs = @('-u', (Join-Path $PSScriptRoot 'gamepad_client.py'),
    '--receiver', $Receiver, '--bind', $BindAddress, '--seconds', $Seconds, '--profile', $Profile)
if (-not $ObserveOnly) {
    $controllerArgs += '--gamepad'
    Write-Host 'Game Bub Xbox controller: keep this console open. Ctrl+C releases and disconnects.'
    if ($Profile -eq 'elden-ring') {
        Write-Host 'Elden Ring: D-pad moves, A attacks(RB), B crouches(L3), X sends LT, Y jumps(A).'
    }
    if ($Profile -eq 'mass-effect') {
        Write-Host 'Mass Effect: D-pad moves; X up/Y left/A right/B down aim; L aims(LT), R fires(RT), Select weapon wheel(LB).'
    }
    if ($Profile -eq 'wow') {
        Write-Host 'WoW: D-pad moves; X up/Y left/A right/B down camera. L/R send LB/RB; Start/Select send Start/Back.'
        Write-Host 'WoW must have native gamepad input enabled. No game bindings are changed by this launcher.'
    }
}
& $controllerPython @controllerArgs
exit $LASTEXITCODE
