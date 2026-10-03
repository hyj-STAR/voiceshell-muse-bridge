# 45-second isolated GATT advertising probe. No account setup or credential access.
$ErrorActionPreference = 'Stop'
$provider = $null
$publisher = $null
$logPath = Join-Path $PSScriptRoot 'advertise-probe.log'
function Log-Status([string]$value) { Add-Content -LiteralPath $logPath -Value ((Get-Date -Format o) + ' ' + $value) }
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $providerType = [Windows.Devices.Bluetooth.GenericAttributeProfile.GattServiceProvider,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
    $resultType = [Windows.Devices.Bluetooth.GenericAttributeProfile.GattServiceProviderResult,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
    $parametersType = [Windows.Devices.Bluetooth.GenericAttributeProfile.GattServiceProviderAdvertisingParameters,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
    $publisherType = [Windows.Devices.Bluetooth.Advertisement.BluetoothLEAdvertisementPublisher,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
    $manufacturerType = [Windows.Devices.Bluetooth.Advertisement.BluetoothLEManufacturerData,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
    $writerType = [Windows.Storage.Streams.DataWriter,Windows.Storage.Streams,ContentType=WindowsRuntime]
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
        $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $operation = $providerType::CreateAsync([Guid]'7fdd3d1c-38ea-46cf-8b46-314ecf5f240c')
    $task = $asTask.MakeGenericMethod($resultType).Invoke($null,@($operation))
    if (-not $task.Wait(15000)) { throw 'TIMEOUT' }
    Log-Status ('SESSION=' + (Get-Process -Id $PID).SessionId + ' CREATE=' + $task.Result.Error)
    if ([string]$task.Result.Error -ne 'Success') { throw 'CREATE_FAILED' }
    $provider = $task.Result.ServiceProvider
    $parameters = [Activator]::CreateInstance($parametersType)
    $parameters.IsConnectable = $true
    $parameters.IsDiscoverable = $true
    $provider.StartAdvertising($parameters)
    Start-Sleep -Seconds 5
    Log-Status ('GATT_ONLY=' + $provider.AdvertisementStatus)
    $publisher = [Activator]::CreateInstance($publisherType)
    $writer = [Activator]::CreateInstance($writerType)
    $writer.WriteByte(0)
    $manufacturer = [Activator]::CreateInstance($manufacturerType)
    $manufacturer.CompanyId = [UInt16]65535
    $manufacturer.Data = $writer.DetachBuffer()
    $publisher.Advertisement.ManufacturerData.Add($manufacturer)
    $publisher.Start()
    Start-Sleep -Seconds 5
    Log-Status ('GATT_WITH_MANUFACTURER=' + $provider.AdvertisementStatus + ' MANUFACTURER=' + $publisher.Status)
    Start-Sleep -Seconds 35
} catch {
    Log-Status ('PROBE_FAILED=' + $_.Exception.GetType().Name)
} finally {
    if ($null -ne $publisher) { $publisher.Stop() }
    if ($null -ne $provider) { $provider.StopAdvertising() }
    Log-Status 'PROBE_CLOSED'
}
