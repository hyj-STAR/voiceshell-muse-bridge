# Read-only Windows PowerShell 5.1 probe. No SDK token or .NET SDK needed.
$ErrorActionPreference = 'Stop'
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $adapterType = [Windows.Devices.Bluetooth.BluetoothAdapter, Windows.Devices.Bluetooth, ContentType=WindowsRuntime]
    $radioType = [Windows.Devices.Radios.Radio, Windows.Devices.Radios, ContentType=WindowsRuntime]
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and
        $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    function Await-WinRT($operation, [Type]$resultType) {
        $task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
        if (-not $task.Wait(15000)) { throw 'WINRT_TIMEOUT' }
        return $task.Result
    }
    $adapter = Await-WinRT ($adapterType::GetDefaultAsync()) $adapterType
    if ($null -eq $adapter) { throw 'ADAPTER_MISSING' }
    $radio = Await-WinRT ($adapter.GetRadioAsync()) $radioType
    [ordered]@{
        adapterPresent = $true
        peripheralRole = $adapter.IsPeripheralRoleSupported
        lowEnergy = $adapter.IsLowEnergySupported
        radio = [string]$radio.State
        realMusePairingVerified = $false
    } | ConvertTo-Json -Compress
} catch {
    Write-Output ('PROBE_FAILED:' + $_.Exception.GetType().Name)
    exit 2
}
