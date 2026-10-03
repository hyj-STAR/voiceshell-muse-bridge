param(
    [Parameter(Mandatory=$true)][string]$PackagePath,
    [Parameter(Mandatory=$true)][string]$PublicCertificatePath,
    [switch]$ConfirmExperimentInstall,
    [switch]$ConfirmMachineTrust
)
$ErrorActionPreference = 'Stop'
if (-not $ConfirmExperimentInstall) { throw 'EXPLICIT_INSTALL_CONFIRMATION_REQUIRED' }
$certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($PublicCertificatePath)
if ($certificate.Subject -ne 'CN=VoiceShell Muse Experiment' -or $certificate.HasPrivateKey -or
    $certificate.NotAfter -lt (Get-Date) -or $certificate.NotAfter -gt (Get-Date).AddDays(2)) { throw 'UNEXPECTED_CERTIFICATE' }
if (Get-AppxPackage -Name VoiceShell.MuseRelayExperimental) { throw 'EXISTING_PACKAGE_NOT_OVERWRITTEN' }
$store = 'Cert:\CurrentUser\TrustedPeople'
if ($ConfirmMachineTrust) {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'ADMINISTRATOR_REQUIRED_FOR_MACHINE_TRUST' }
    $store = 'Cert:\LocalMachine\TrustedPeople'
}
$prior = Test-Path ($store + '\' + $certificate.Thumbprint)
if (-not $prior) { Import-Certificate -FilePath $PublicCertificatePath -CertStoreLocation $store | Out-Null }
try {
    Add-AppxPackage -Path $PackagePath
    $package = Get-AppxPackage -Name VoiceShell.MuseRelayExperimental
    if ($null -eq $package) { throw 'PACKAGE_REGISTRATION_NOT_VERIFIED' }
    [ordered]@{ name = $package.Name; version = [string]$package.Version; installed = $true } | ConvertTo-Json -Compress
} catch {
    if (-not $prior) { Remove-Item -LiteralPath ($store + '\' + $certificate.Thumbprint) }
    throw
}
