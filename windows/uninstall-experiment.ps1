param(
    [Parameter(Mandatory=$true)][string]$PublicCertificatePath,
    [switch]$ConfirmExperimentRemoval,
    [switch]$RemoveMachineTrust
)
$ErrorActionPreference = 'Stop'
if (-not $ConfirmExperimentRemoval) { throw 'EXPLICIT_REMOVAL_CONFIRMATION_REQUIRED' }
$certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($PublicCertificatePath)
if ($certificate.Subject -ne 'CN=VoiceShell Muse Experiment' -or $certificate.HasPrivateKey) { throw 'UNEXPECTED_CERTIFICATE' }
$store = 'Cert:\CurrentUser\TrustedPeople'
if ($RemoveMachineTrust) {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'ADMINISTRATOR_REQUIRED_FOR_MACHINE_TRUST' }
    $store = 'Cert:\LocalMachine\TrustedPeople'
}
$package = Get-AppxPackage -Name VoiceShell.MuseRelayExperimental
if ($package) { Remove-AppxPackage -Package $package.PackageFullName }
$path = $store + '\' + $certificate.Thumbprint
if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
[ordered]@{
    packageInstalled=[bool](Get-AppxPackage -Name VoiceShell.MuseRelayExperimental)
    certificateTrusted=(Test-Path -LiteralPath $path)
} | ConvertTo-Json -Compress
