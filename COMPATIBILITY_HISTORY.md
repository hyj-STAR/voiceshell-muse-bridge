# Historical compatibility log — superseded checkpoints

This preserves the earlier Mac/Windows/ESP32 investigation unchanged below.
Statements such as “not paired” refer to those earlier checkpoints, not the
latest ESP32 and Linux results. See [current overview](README.md) and
[Linux migration evidence](voice_out/LINUX_MIGRATION_20261003.md).

# VoiceShell Muse Bridge — compatibility experiment

This is research source, **not a working Muse integration or official Windows/Mac SDK**.
No website/release claims of successful account pairing have been made.

## Current evidence (2026-10-03)

| Layer | Observed result |
| --- | --- |
| Official Linux SDK tests | 137 passed locally and on isolated Debian server |
| SSH encrypted setup transport tests | 6 passed with mocked authorization persistence |
| Mac GATT registration / advertising | OS callback succeeded |
| Real iPhone Muse discovery of Mac relay | Failed in repeated user attempts; no pairing |
| Windows peripheral capability probe | Physical Windows adapter reports peripheralRole=true, lowEnergy=true, radio=On |
| Windows GATT advertising | Aborted by Windows in SSH session 0; GATT-only probe also Aborted in logged-in desktop session 1 |
| Windows Muse discovery / pairing | Not achieved; account remains unpaired |
| ESP32-S3 actual phone discovery | User confirmed MuseGadget appears in Muse App |
| ESP32-S3 BOOT confirmation / Wi-Fi | Passed; user confirmed the network is a phone hotspot |
| ESP32-S3 cloud VM lookup | Socket timeouts / HTTP status 0; binding did not complete |
| Voice Out text bridge | 8 local tests passed; isolated Linux service deployed; synthetic queue roundtrip passed |
| Account binding / live Muse reply / earphone playback | Not verified |

## Voice Out Bridge

See [voice_out/README.md](voice_out/README.md) for the new single-owner experimental
text-output interface and restricted official Linux SDK adapter. This component
does not provide a network proxy for ESP32 pairing, nor does it establish a Muse
account binding. It never exposes the SDK's default shell/file commands.
Deployment evidence and incomplete gates: [voice_out/DEPLOYMENT.md](voice_out/DEPLOYMENT.md).

After user-approved adapter restart, Windows PnP returned 3010 (whole-system restart
required). At that checkpoint the computer was not rebooted automatically. A subsequent relay attempt
still returned GATT Aborted and manufacturer-advertisement RadioNotAvailable, while
the separate capability query reported radio On. Pairing remains unsuccessful; a
capability flag is not proof of working advertisement delivery.

The user subsequently approved a system reboot. SSH returned and the read-back boot
time was 2026-10-03 15:11:45 (UTC+8). Both the SSH-session relay and the logged-in
desktop-session GATT-only probe still returned Aborted after reboot. Restart did
not solve the observed advertising failure. Temporary desktop probe tasks were
removed; account authorization was not established.

An updated Muse app exposed the Add Device entry that was absent before updating.
Discovery failure after that is a separate compatibility issue. No server shell-command
executor is started by this experiment.

## Windows experiment

Requires Windows 10 2004+ / Windows 11, .NET 8 SDK, OpenSSH client, Bluetooth ON,
and a Bluetooth adapter whose driver reports `IsPeripheralRoleSupported`.
Default run is read-only capability detection:

```powershell
cd windows
dotnet run -- --probe
```

Without the .NET SDK, Windows PowerShell 5.1 can run `./probe.ps1` instead.
The probe does not enable Bluetooth, change pairing or start advertisements.

`advertise-probe.ps1` is a separate, short-lived advertising diagnostic. It does
change radio advertising temporarily, logs metadata only, and stops its own
advertisements. It is NOT a pairing implementation. On the tested machine its
desktop-session GATT-only attempt returned Aborted; a subsequent PowerShell
manufacturer-data setup raised SetValueInvocationException, so that phase did
not produce a valid compatibility result. Do not infer that all Windows hardware
fails or that the SSH session alone caused the failure.

The GATT relay is **experimental**, not claimed compatible. Windows GATT uses the
system friendly name; this program does NOT rename the computer. A separate
manufacturer-data advertisement is attempted, but whether the OS/controller combines
it with GATT advertisements in a way Muse accepts remains unverified. The explicit
flag acknowledges those limitations:

```powershell
dotnet run -- --relay YOUR_SSH_ALIAS "YOUR_ISOLATED_BACKEND_COMMAND" --allow-name-mismatch
```

Run the pinned official Linux SDK plus `server_pairing_relay.py` at the destination.
The SSH command should select an isolated `MUSEGADGET_STATE_DIR`, set `PYTHONPATH`
to the SDK's `linux/src`, and run the backend using its own Python environment.
Put your personal SDK token in that **server-side private state directory**, outside Git.
No real token, account state, private machine address or production paths are supplied here.
SSH authentication must already work; this program neither changes SSH configuration
nor disables host-key checks. Ctrl+C or ten minutes closes the experimental broadcasts.

Alternatively, run `run_windows_relay.py` on a coordinator already authorized to SSH
to both hosts. Supply the Windows executable command with
`--stdio --allow-name-mismatch`, and the isolated backend command. Both subprocesses
are outbound SSH: no listener, copied private key or token on Windows is required.
The Windows host still must be physically near the phone; Tailscale does not forward
Bluetooth radio advertisements. This coordinator mode is experimental too.

`GATT_ADVERTISEMENT`/`MANUFACTURER_ADVERTISEMENT` are OS statuses, **not proof of
phone discovery**. `PHONE_SUBSCRIBED`/`PHONE_WRITE` are progress, not authorization.
`SERVER_AUTHORIZATION_SAVED_NO_CONTROL_EXECUTOR` confirms backend persistence only;
phone UI confirmation, network reconnect and task execution still require separate tests.

## Protocol / safety

Run the six transport tests using a separately cloned official SDK at the pinned commit:

```sh
export MUSE_SDK_LINUX_DIR=/path/to/muse-gadget-sdk/linux
uv run --with pytest --with "$MUSE_SDK_LINUX_DIR" python -m pytest test_relay.py -q
```

- Uses official service/RX/TX UUIDs and official encrypted pairing controller.
- SSH stdio transports encrypted BLE packet bytes; logs contain status labels only.
- Rejects multiple phone clients, oversized packets and malformed events.
- Does not bypass phone authorization or create fabricated device credentials.
- Does not change the AC7912 firmware, VoiceShell client, Bluetooth pairings or firewall.
- Windows GATT lifecycle after stopping advertising still needs device testing; exit
  the process when finished. Do not install a persistent background service.

## Why the Mac experiment may fail

Official BlueZ advertises manufacturer company `0xFFFF` with an unpaired flag and
sets both local and GAP names. CoreBluetooth's public peripheral API only supports
local-name and service-UUID advertising. The missing fields are a compatibility
hypothesis, **not a proven unique cause of the observed discovery failure**.

## Release gate

The package-identity hypothesis has a separate MSIX declaring
Bluetooth capability and ordinary-user Win32 execution. The diagnostic mode
`--advertise-probe NEW_LOG_PATH` runs for 45 seconds, records actual package identity
and advertising statuses, and never performs account pairing. Windows system access
queries returned Allowed and privacy consent Allow, so a globally disabled Bluetooth
permission is not supported by the observed evidence. Package-level effects remain
unverified until the packaged executable runs on the real machine.

For local testing, CI signs the package with a fresh one-day, non-exportable key on
the disposable runner. Only the signed MSIX and PUBLIC certificate are uploaded;
no account token, repository secret or private signing key is exported. Installation
requires explicit user approval before trusting that certificate. On 2026-10-03,
the user approved CurrentUser TrustedPeople only. That installation actually failed
with `0x800B0109`; the installer catch path removed the newly imported certificate.
The packaged advertising probe has therefore NOT run, and pairing remains unverified.
Microsoft's MSIX troubleshooting guide requires LocalMachine TrustedPeople for this
failure. That machine-wide trust change requires separate approval and elevation;
the current installer deliberately does not attempt it or import anything into Root.
The user subsequently approved the necessary scoped machine trust for this experiment.
The installer now requires an additional `-ConfirmMachineTrust` flag and checks
administrator rights before using LocalMachine TrustedPeople. This cleared certificate
validation, but the first real install then failed with `0x80080204`: the `win32App`
runtime declaration required `unvirtualizedResources`. The package declaration was
changed to `packagedClassicApp` instead of adding that capability. The failed attempt
rolled back its certificate import. Compilation/package generation is not installation
or phone-discovery evidence.
The corrected package then installed successfully on the real Windows machine
(`VoiceShell.MuseRelayExperimental`, version `0.1.0.0`). A limited-rights interactive
desktop task launched the 45-second advertising probe. Its log initially remained
locked by the diagnostic writer, so no advertising status could yet be read.
Before the final log could be retrieved, the Windows Tailscale peer went offline;
SSH and Tailscale ping timed out. Advertising, package identity at runtime, and real
Muse pairing therefore remain unverified. Package/certificate removal and temporary
task cleanup were pending reconnection at that checkpoint.
After reconnection, the real log confirmed package identity, radio On, successful
service/characteristic creation, GATT Aborted, and manufacturer-data Started. Thus
package identity and capability declaration did not fix connectable GATT advertising.
The probe finished normally and its temporary scheduled task was removed. See
`evidence/windows-packaged-probe-20261003.txt`. Package/certificate removal is still
pending while the follow-up diagnostic experiment is in progress.
The follow-up packaged probe also returned Aborted with connectable=false /
discoverable=true, and connectable=true / discoverable=false. Manufacturer advertising
again returned Started. See `evidence/windows-gatt-matrix-20261003.txt`. This narrows
the observed failure to GATT publishing on this tested configuration; it does NOT
prove that driver age, hardware, or all Windows implementations are the cause.
After the matrix test, the experimental package and its exact LocalMachine
TrustedPeople certificate were removed; readback reported both false. Both temporary
desktop tasks were removed. No pairing credentials were created by either probe.
It is not a production release or broadly trusted signer.
The installer refuses to overwrite an existing experimental package. Uninstall the
named experimental package and remove only this certificate when the test ends.
`uninstall-experiment.ps1` removes only the current user's exact experimental package
and the certificate identified by its public certificate file; machine-store removal
requires the explicit `-RemoveMachineTrust` flag and administrator rights.

Before public promotion: real phone discovers device → user approves community device
permissions → encrypted setup → backend verifies and persists authorization → phone
shows paired → least-privilege runtime reconnect → a real round-trip message test.
Commercial/public product integration also needs review of current Muse SDK access
terms; Apache-2.0 source licensing alone does not grant commercial token access.
Never purchase artificial stars or publish a fabricated adoption count.

## References

- Official SDK commit: `d62b72f8f76b4c18cf9aa64dd3b8781a4f31f7c4`
- https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux
- https://learn.microsoft.com/en-us/windows/apps/develop/devices-sensors/gatt-server
- https://learn.microsoft.com/en-us/windows/msix/msix-troubleshooting-guide
- https://learn.microsoft.com/en-us/uwp/api/windows.devices.bluetooth.advertisement.bluetoothleadvertisementpublisher
- https://developer.apple.com/documentation/corebluetooth/cbperipheralmanager/startadvertising(_:)
- https://gadgets.muse.ai/sdk-terms
