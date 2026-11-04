<#
.SYNOPSIS
Stage or install the signed ViGEmBus driver without restarting Windows or Sunshine.
#>
param([switch]$Install)
$ErrorActionPreference = 'Stop'
$controllerArtifacts = Join-Path $PSScriptRoot 'artifacts\controller-setup-20261103'
New-Item -ItemType Directory -Path $controllerArtifacts -Force | Out-Null
$controllerInstaller = Join-Path $controllerArtifacts 'ViGEmBus_1.22.0_x64_x86_arm64.exe'
$controllerUrl = 'https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBus_1.22.0_x64_x86_arm64.exe'
$controllerExpectedHash = '89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A'
if (-not (Test-Path -LiteralPath $controllerInstaller)) {
    Invoke-WebRequest -UseBasicParsing -Uri $controllerUrl -OutFile $controllerInstaller
}
$controllerSignature = Get-AuthenticodeSignature -LiteralPath $controllerInstaller
$controllerHash = (Get-FileHash -LiteralPath $controllerInstaller -Algorithm SHA256).Hash
if ($controllerHash -ne $controllerExpectedHash -or $controllerSignature.Status -ne 'Valid' -or
    $controllerSignature.SignerCertificate.Subject -notmatch 'Nefarius Software Solutions') {
    throw 'Controller installer hash or Authenticode verification failed; nothing was installed.'
}
if (-not $Install) {
    [pscustomobject]@{Installer=$controllerInstaller;SHA256=$controllerHash;Signature='Valid';Installed=$false} | ConvertTo-Json
    exit 0
}
$controllerIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$controllerPrincipal = [Security.Principal.WindowsPrincipal]::new($controllerIdentity)
if (-not $controllerPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    try {
        $controllerElevated = Start-Process -FilePath 'powershell.exe' -Verb RunAs -WindowStyle Hidden -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Install'
        ) -Wait -PassThru
        exit $controllerElevated.ExitCode
    } catch {
        @{Status='AdministratorConsentNotCompleted';Error=$_.Exception.Message} | ConvertTo-Json |
            Set-Content -LiteralPath (Join-Path $controllerArtifacts 'installation-result.json')
        throw
    }
}
$controllerInstallProcess = Start-Process -FilePath $controllerInstaller -WindowStyle Hidden -ArgumentList @(
    '/exenoui', '/qn', '/norestart'
) -Wait -PassThru
$controllerResult = @{
    InstallerExitCode=$controllerInstallProcess.ExitCode
    RestartRequired=($controllerInstallProcess.ExitCode -eq 3010)
    Installer=$controllerInstaller
    SHA256=$controllerHash
    Signature='Valid'
    SunshineRestartRequested=$false
    WindowsRestartRequested=$false
    InstallerArguments=@('/exenoui','/qn','/norestart')
}
$controllerResult | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $controllerArtifacts 'installation-result.json')
if ($controllerInstallProcess.ExitCode -notin @(0,3010)) {
    throw "Controller driver installation failed: $($controllerInstallProcess.ExitCode). See installation-result.json."
}
$controllerResult | ConvertTo-Json
