<#
.SYNOPSIS
Launch the finite experimental JPEG/audio/controller sender with explicit modes.
.DESCRIPTION
No installed Sunshine service or game settings are changed. Stop any existing
AV session first. Logs never overwrite existing evidence directories.
#>
param(
    [Parameter(Mandatory=$true)][string]$Receiver,
    [string]$BindAddress = '192.168.0.47',
    [ValidateRange(1,7200)][int]$Seconds = 60,
    [Parameter(Mandatory=$true)][uint32]$StartFrameId,
    [Parameter(Mandatory=$true)][string]$Output,
    [switch]$Video,
    [string]$Clip,
    [switch]$LoopClip,
    [ValidateSet('legacy','native')][string]$ClipSelection = 'legacy',
    [switch]$Audio,
    [switch]$Gamepad,
    [switch]$AvInput,
    [switch]$DryRun,
    [ValidateSet('standard','elden-ring','mass-effect','wow')][string]$Profile = 'standard',
    [ValidateRange(1,30)][int]$FPS = 5,
    [ValidateSet('sleep','precise','hybrid')][string]$PacingWait = 'sleep',
    [ValidateRange(0,1000)][int]$PacingSpinUs = 600,
    [ValidateRange(0,65535)][int]$VideoSourcePort = 0,
    [ValidateRange(0,65535)][int]$AvSourcePort = 0,
    [string]$CaptureInterface,
    [string]$CaptureExecutable = 'C:\Program Files\Wireshark\dumpcap.exe',
    [ValidateRange(1,95)][int]$Quality = 25,
    [double]$Mbps = 2,
    [ValidateRange(0,1)][double]$Gain = 0.75
)
$ErrorActionPreference = 'Stop'
$sessionPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$sessionArgs = @('-u',(Join-Path $PSScriptRoot 'session_launcher.py'),'--receiver',$Receiver,
    '--bind',$BindAddress,'--seconds',$Seconds,'--start-frame-id',$StartFrameId,
    '--output',$Output,'--profile',$Profile,'--fps',$FPS,'--quality',$Quality,
    '--mbps',$Mbps,'--gain',$Gain)
if ($Video) {$sessionArgs += '--video'}
if ($Clip) {$sessionArgs += @('--clip',$Clip)}
if ($LoopClip) {$sessionArgs += '--loop-clip'}
if ($ClipSelection -ne 'legacy') {$sessionArgs += @('--clip-selection',$ClipSelection)}
if ($Audio) {$sessionArgs += '--audio'}
if ($Gamepad) {$sessionArgs += '--gamepad'}
if ($AvInput) {$sessionArgs += '--av-input'}
if ($PacingWait -ne 'sleep') {$sessionArgs += @('--pacing-wait',$PacingWait)}
if ($PacingSpinUs -ne 600) {$sessionArgs += @('--pacing-spin-us',$PacingSpinUs)}
if ($VideoSourcePort) {$sessionArgs += @('--video-source-port',$VideoSourcePort)}
if ($AvSourcePort) {$sessionArgs += @('--av-source-port',$AvSourcePort)}
if ($CaptureInterface) {$sessionArgs += @('--capture-interface',$CaptureInterface,'--capture-executable',$CaptureExecutable)}
if ($DryRun) {$sessionArgs += '--dry-run'}
& $sessionPython @sessionArgs
exit $LASTEXITCODE
