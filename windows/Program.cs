using System.Diagnostics;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Text.Json;
using System.Threading.Channels;
using Windows.Devices.Bluetooth;
using Windows.Devices.Bluetooth.Advertisement;
using Windows.Devices.Bluetooth.GenericAttributeProfile;

// Experimental transport only: never starts a shell-command executor for Muse.
internal static class Program
{
    private static readonly Guid ServiceId = new("7fdd3d1c-38ea-46cf-8b46-314ecf5f240c");
    private static readonly Guid RxId = new("4d593029-28a2-4a6e-a1f0-3c2d5e8f9b01");
    private static readonly Guid TxId = new("d75dc4ca-7b2b-4e9c-8f0a-1d2e3f4a5b6c");
    private static readonly TextWriter ProtocolOutput = Console.Out;

    public static async Task<int> Main(string[] args)
    {
        var stdio = args.SequenceEqual(new[] { "--stdio", "--allow-name-mismatch" });
        var advertiseProbe = args.Length == 2 && args[0] == "--advertise-probe";
        using var probeLog = advertiseProbe ? new StreamWriter(File.Open(args[1], FileMode.CreateNew, FileAccess.Write, FileShare.Read)) { AutoFlush = true } : null;
        if (probeLog is not null) Console.SetOut(probeLog);
        if (stdio) Console.SetOut(Console.Error); // stdout is reserved for encrypted packet events.
        if (!OperatingSystem.IsWindows()) return 2;
        try
        {
            try { Console.WriteLine("PACKAGE_IDENTITY:" + Windows.ApplicationModel.Package.Current.Id.Name); }
            catch { Console.WriteLine("PACKAGE_IDENTITY:UNPACKAGED"); }
            var adapter = await BluetoothAdapter.GetDefaultAsync();
            if (adapter is null) { Console.WriteLine("BLUETOOTH_ADAPTER_MISSING"); return 2; }
            var radio = await adapter.GetRadioAsync();
            Console.WriteLine(JsonSerializer.Serialize(new {
                os = Environment.OSVersion.Version.ToString(),
                adapterPresent = true, peripheralRole = adapter.IsPeripheralRoleSupported,
                lowEnergy = adapter.IsLowEnergySupported, radio = radio?.State.ToString(),
                realMusePairingVerified = false
            }));
            if (args.Length == 0 || args.SequenceEqual(new[] { "--probe" })) return 0;
            if (advertiseProbe) {
                using var probeTimeout = new CancellationTokenSource(TimeSpan.FromSeconds(45));
                await RunAdvertisingProbe(probeTimeout.Token); return 0;
            }
            if (stdio) {
                if (!adapter.IsPeripheralRoleSupported || radio?.State != Windows.Devices.Radios.RadioState.On)
                { Console.WriteLine("PERIPHERAL_ROLE_OR_RADIO_UNAVAILABLE"); return 2; }
                using var stdioTimeout = new CancellationTokenSource(TimeSpan.FromMinutes(10));
                await RunRelay(null, null, stdioTimeout); return 0;
            }
            if (args.Length != 4 || args[0] != "--relay" || args[3] != "--allow-name-mismatch")
            {
                Console.WriteLine("Usage: --probe OR --relay SSH_HOST REMOTE_COMMAND --allow-name-mismatch");
                return 2;
            }
            if (!adapter.IsPeripheralRoleSupported || radio?.State != Windows.Devices.Radios.RadioState.On)
            { Console.WriteLine("PERIPHERAL_ROLE_OR_RADIO_UNAVAILABLE"); return 2; }
            Console.WriteLine("EXPERIMENT: Windows friendly/GAP name is not changed. Manufacturer broadcast may not merge with GATT broadcast. Discovery is NOT guaranteed.");
            using var timeout = new CancellationTokenSource(TimeSpan.FromMinutes(10));
            Console.CancelKeyPress += (_, e) => { e.Cancel = true; timeout.Cancel(); };
            await RunRelay(args[1], args[2], timeout);
            return 0;
        }
        catch (OperationCanceledException) { Console.WriteLine("PAIRING_WINDOW_CLOSED"); return 0; }
        catch (Exception error)
        {
            // Exception messages can contain payloads/paths: report type only.
            Console.WriteLine("EXPERIMENT_FAILED:" + error.GetType().Name);
            return 2;
        }
    }

    private static async Task RunAdvertisingProbe(CancellationToken token)
    {
        var result = await GattServiceProvider.CreateAsync(ServiceId);
        Console.WriteLine("PROBE_SERVICE_CREATE:" + result.Error);
        if (result.Error != BluetoothError.Success) return;
        var provider = result.ServiceProvider;
        BluetoothLEAdvertisementPublisher? publisher = null;
        try {
            var characteristic = await provider.Service.CreateCharacteristicAsync(TxId,
                new GattLocalCharacteristicParameters {
                    CharacteristicProperties = GattCharacteristicProperties.Read,
                    StaticValue = new byte[] { 0 }.AsBuffer(), ReadProtectionLevel = GattProtectionLevel.Plain
                });
            Console.WriteLine("PROBE_CHARACTERISTIC_CREATE:" + characteristic.Error);
            if (characteristic.Error != BluetoothError.Success) return;
            provider.AdvertisementStatusChanged += (_, e) => Console.WriteLine("GATT_ADVERTISEMENT:" + e.Status + ":" + e.Error);
            provider.StartAdvertising(new GattServiceProviderAdvertisingParameters { IsDiscoverable = true, IsConnectable = true });
            await Task.Delay(4000, token);
            Console.WriteLine("GATT_ONLY_STATUS:" + provider.AdvertisementStatus);
            if (provider.AdvertisementStatus == GattServiceProviderAdvertisementStatus.Aborted) {
                // Isolate connectable versus discoverable requests without another publisher.
                foreach (var flags in new[] { (connectable: false, discoverable: true), (connectable: true, discoverable: false) }) {
                    provider.StopAdvertising();
                    await Task.Delay(1000, token);
                    provider.StartAdvertising(new GattServiceProviderAdvertisingParameters {
                        IsConnectable = flags.connectable, IsDiscoverable = flags.discoverable
                    });
                    await Task.Delay(4000, token);
                    Console.WriteLine($"GATT_VARIANT:connectable={flags.connectable}:discoverable={flags.discoverable}:status={provider.AdvertisementStatus}");
                }
                provider.StopAdvertising();
                await Task.Delay(1000, token);
                provider.StartAdvertising(new GattServiceProviderAdvertisingParameters { IsDiscoverable = true, IsConnectable = true });
                await Task.Delay(4000, token);
            }
            publisher = new BluetoothLEAdvertisementPublisher();
            publisher.Advertisement.ManufacturerData.Add(new BluetoothLEManufacturerData(0xFFFF, new byte[] { 0 }.AsBuffer()));
            publisher.StatusChanged += (_, e) => Console.WriteLine("MANUFACTURER_ADVERTISEMENT:" + e.Status + ":" + e.Error);
            publisher.Start();
            await Task.Delay(4000, token);
            Console.WriteLine("COMBINED_STATUS:" + provider.AdvertisementStatus + ":" + publisher.Status);
            await Task.Delay(Timeout.Infinite, token);
        } finally { publisher?.Stop(); provider.StopAdvertising(); Console.WriteLine("PROBE_CLOSED_NO_ACCOUNT_PAIRING"); }
    }

    private static async Task RunRelay(string? host, string? command, CancellationTokenSource lifetime)
    {
        if (host is not null && (host.StartsWith('-') || host.Any(char.IsWhiteSpace))) throw new ArgumentException();
        var info = new ProcessStartInfo("ssh") { RedirectStandardInput = true,
            RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false };
        if (host is not null) foreach (var argument in new[] { "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, command! })
            info.ArgumentList.Add(argument);
        using var ssh = host is null ? null : Process.Start(info) ?? throw new InvalidOperationException();
        TextReader incoming = ssh is null ? Console.In : ssh.StandardOutput;
        TextWriter outgoing = ssh is null ? ProtocolOutput : ssh.StandardInput;
        var stderr = ssh is null ? Task.CompletedTask : Task.Run(async () => { while (await ssh.StandardError.ReadLineAsync() is not null) { } });
        using var inputLock = new SemaphoreSlim(1);
        async Task Send(object data)
        {
            await inputLock.WaitAsync(lifetime.Token);
            try { await outgoing.WriteLineAsync(JsonSerializer.Serialize(data)); await outgoing.FlushAsync(); }
            finally { inputLock.Release(); }
        }
        GattServiceProvider? provider = null;
        BluetoothLEAdvertisementPublisher? publisher = null;
        try
        {
            var readyLine = await incoming.ReadLineAsync(lifetime.Token);
            if (readyLine is null || readyLine.Length > 32768) throw new InvalidOperationException();
            using var ready = JsonDocument.Parse(readyLine);
            var name = ready.RootElement.GetProperty("name").GetString();
            if (ready.RootElement.GetProperty("event").GetString() != "ready" ||
                name is null || name.Length != 16 || !name.StartsWith("MuseGadget")) throw new InvalidOperationException();
            Console.WriteLine("SERVER_READY:" + name);
            var result = await GattServiceProvider.CreateAsync(ServiceId);
            if (result.Error != BluetoothError.Success) throw new InvalidOperationException();
            provider = result.ServiceProvider;
            var rx = await provider.Service.CreateCharacteristicAsync(RxId, new GattLocalCharacteristicParameters {
                CharacteristicProperties = GattCharacteristicProperties.Write | GattCharacteristicProperties.WriteWithoutResponse,
                WriteProtectionLevel = GattProtectionLevel.Plain });
            var tx = await provider.Service.CreateCharacteristicAsync(TxId, new GattLocalCharacteristicParameters {
                CharacteristicProperties = GattCharacteristicProperties.Read | GattCharacteristicProperties.Notify,
                ReadProtectionLevel = GattProtectionLevel.Plain });
            if (rx.Error != BluetoothError.Success || tx.Error != BluetoothError.Success) throw new InvalidOperationException();
            var packets = Channel.CreateBounded<byte[]>(new BoundedChannelOptions(512) {
                FullMode = BoundedChannelFullMode.Wait, SingleReader = true, SingleWriter = true });
            var changed = new SemaphoreSlim(0);
            var stateLock = new object();
            string? owner = null;
            GattSubscribedClient? client = null;
            tx.Characteristic.ReadRequested += async (_, e) => {
                var deferral = e.GetDeferral();
                try {
                    var request = await e.GetRequestAsync();
                    request?.RespondWithValue(Array.Empty<byte>().AsBuffer());
                } catch { lifetime.Cancel(); } finally { deferral.Complete(); }
            };
            tx.Characteristic.SubscribedClientsChanged += async (sender, _) => {
                try {
                    lock (stateLock) {
                        var clients = sender.SubscribedClients;
                        if (clients.Count > 1) { lifetime.Cancel(); return; }
                        client = clients.SingleOrDefault();
                        if (client is not null) {
                            var id = client.Session.DeviceId.Id;
                            if (owner is not null && owner != id) { lifetime.Cancel(); return; }
                            owner = id;
                        }
                    }
                    if (client is not null) {
                        await Send(new { @event = "mtu", value = Math.Min(163, (int)client.MaxNotificationSize + 3) });
                        Console.WriteLine("PHONE_SUBSCRIBED"); changed.Release();
                    } else { await Send(new { @event = "disconnect" }); }
                } catch { lifetime.Cancel(); }
            };
            rx.Characteristic.WriteRequested += async (_, e) => {
                var deferral = e.GetDeferral();
                try {
                    var request = await e.GetRequestAsync();
                    if (request is null) return;
                    var id = e.Session.DeviceId.Id;
                    lock (stateLock) {
                        if (owner is not null && owner != id) {
                            request.RespondWithProtocolError(0x0E); lifetime.Cancel(); return;
                        }
                        owner = id;
                    }
                    var bytes = request.Value.ToArray();
                    if (bytes.Length > 512) { request.RespondWithProtocolError(0x0D); return; }
                    await Send(new { @event = "write", data = Convert.ToBase64String(bytes) });
                    if (request.Option == GattWriteOption.WriteWithResponse) request.Respond();
                    Console.WriteLine("PHONE_WRITE");
                } catch { lifetime.Cancel(); } finally { deferral.Complete(); }
            };
            provider.AdvertisementStatusChanged += (_, e) => {
                Console.WriteLine("GATT_ADVERTISEMENT:" + e.Status + ":" + e.Error);
                if (e.Status == GattServiceProviderAdvertisementStatus.Aborted) lifetime.Cancel();
            };
            provider.StartAdvertising(new GattServiceProviderAdvertisingParameters { IsConnectable = true, IsDiscoverable = true });
            publisher = new BluetoothLEAdvertisementPublisher();
            // LocalName and ServiceUuids are RESERVED on this publisher: never set them.
            publisher.Advertisement.ManufacturerData.Add(new BluetoothLEManufacturerData(0xFFFF, new byte[] { 0 }.AsBuffer()));
            publisher.StatusChanged += (_, e) => {
                Console.WriteLine("MANUFACTURER_ADVERTISEMENT:" + e.Status + ":" + e.Error);
                if (e.Status == BluetoothLEAdvertisementPublisherStatus.Aborted) lifetime.Cancel();
            };
            publisher.Start();
            var notifications = Task.Run(async () => {
                try {
                    await foreach (var packet in packets.Reader.ReadAllAsync(lifetime.Token)) {
                        GattSubscribedClient? target;
                        while (true) {
                            lock (stateLock) target = client;
                            if (target is not null) break;
                            await changed.WaitAsync(lifetime.Token);
                        }
                        if (packet.Length > target.MaxNotificationSize) throw new InvalidOperationException();
                        var sent = await tx.Characteristic.NotifyValueAsync(packet.AsBuffer(), target);
                        if (sent.Status != GattCommunicationStatus.Success) throw new InvalidOperationException();
                    }
                } catch { lifetime.Cancel(); }
            });
            while (!lifetime.IsCancellationRequested) {
                var line = await incoming.ReadLineAsync(lifetime.Token);
                if (line is null || line.Length > 32768) throw new InvalidOperationException();
                using var message = JsonDocument.Parse(line);
                var value = message.RootElement;
                switch (value.GetProperty("event").GetString()) {
                    case "packet":
                        var packet = Convert.FromBase64String(value.GetProperty("data").GetString()!);
                        if (packet.Length > 160) throw new InvalidOperationException();
                        await packets.Writer.WriteAsync(packet, lifetime.Token); break;
                    case "complete":
                        // Keep TX alive briefly so queued auth_ok can reach the phone.
                        Console.WriteLine("SERVER_AUTHORIZATION_SAVED_NO_CONTROL_EXECUTOR");
                        await Task.Delay(2000, lifetime.Token); lifetime.Cancel(); break;
                    case "disconnect":
                        await Task.Delay(2000, lifetime.Token); lifetime.Cancel(); break;
                    default: throw new InvalidOperationException();
                }
            }
            packets.Writer.TryComplete();
            await notifications;
        }
        finally {
            lifetime.Cancel();
            publisher?.Stop(); provider?.StopAdvertising();
            if (ssh is not null) {
                if (!ssh.HasExited) ssh.Kill(true);
                await ssh.WaitForExitAsync();
            }
            await stderr;
        }
    }
}
