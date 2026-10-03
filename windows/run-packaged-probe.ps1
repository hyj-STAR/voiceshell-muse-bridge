param([Parameter(Mandatory=$true)][string]$LogPath)
$ErrorActionPreference = 'Stop'
$package = Get-AppxPackage -Name VoiceShell.MuseRelayExperimental
if ($null -eq $package) { throw 'EXPERIMENT_PACKAGE_MISSING' }
if (Test-Path -LiteralPath $LogPath) { throw 'PROBE_LOG_ALREADY_EXISTS' }
$executable = Join-Path $package.InstallLocation 'MuseRelay.exe'
# Interactive desktop execution is arranged by the caller. Runs as current user.
& $executable --advertise-probe $LogPath
exit $LASTEXITCODE
