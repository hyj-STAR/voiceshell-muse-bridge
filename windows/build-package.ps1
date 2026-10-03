param([Parameter(Mandatory=$true)][string]$BuildDirectory)
$ErrorActionPreference = 'Stop'
$target = Join-Path $BuildDirectory 'package-layout'
New-Item -ItemType Directory -Path $target -Force | Out-Null
Get-ChildItem -LiteralPath $BuildDirectory -File | Copy-Item -Destination $target
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'AppxManifest.xml') -Destination $target
$assets = Join-Path $target 'Assets'
New-Item -ItemType Directory -Path $assets -Force | Out-Null
Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap(150,150)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.Clear([System.Drawing.Color]::FromArgb(51,85,170))
$bitmap.Save((Join-Path $assets 'Logo.png'),[System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose(); $bitmap.Dispose()
$makeappx = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe' | Sort-Object FullName -Descending | Select-Object -First 1
if ($null -eq $makeappx) { throw 'WINDOWS_PACKAGING_SDK_MISSING' }
& $makeappx.FullName pack /d $target /p (Join-Path $BuildDirectory 'MuseRelay-unsigned.msix') /o
if ($LASTEXITCODE -ne 0) { throw 'PACKAGE_VALIDATION_FAILED' }
# Ephemeral code-signing key belongs only to this disposable runner. It is
# non-exportable; export ONLY the public certificate, never PFX/private key.
$certificate = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=VoiceShell Muse Experiment' -CertStoreLocation 'Cert:\CurrentUser\My' -KeyExportPolicy NonExportable -NotAfter (Get-Date).AddDays(1)
$signtool = Join-Path $makeappx.DirectoryName 'signtool.exe'
& $signtool sign /fd SHA256 /sha1 $certificate.Thumbprint /s My (Join-Path $BuildDirectory 'MuseRelay-unsigned.msix')
if ($LASTEXITCODE -ne 0) { throw 'PACKAGE_SIGNING_FAILED' }
Move-Item -LiteralPath (Join-Path $BuildDirectory 'MuseRelay-unsigned.msix') -Destination (Join-Path $BuildDirectory 'MuseRelay-experimental.msix')
Export-Certificate -Cert $certificate -FilePath (Join-Path $BuildDirectory 'MuseRelay-experimental-public.cer') | Out-Null
# No repository secrets, private-key export or target-machine installation.
