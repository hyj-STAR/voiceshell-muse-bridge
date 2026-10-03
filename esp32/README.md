# ESP32-S3 pairing experiment

> **Update, 2026-10-03:** Pairing and cloud connectivity subsequently succeeded.
> Three text round trips passed; Linux later completed two independent sessions
> with the ESP32 application stopped. See [serial bridge](SERIAL_CHAT.md) and
> [Linux evidence](../voice_out/LINUX_MIGRATION_20261003.md).
> The network-blocker narrative below preserves the earlier checkpoint, not current status.

Status: original Flash backup verified; pinned SDK built and flashed with write verification. After a physical RESET/EN without BOOT held, the application emitted stable heartbeats and reported BLE `advertising` with 8,160 KiB PSRAM available. The user confirmed **Muse App can see the MuseGadget device**. Physical button confirmation and Wi-Fi joining also passed, but pairing failed during cloud VM lookup: repeated socket connection timeouts with no HTTP response. Account binding and the cloud connection are **not complete**. This is not a VoiceShell production firmware or an audio integration.

## Pinned inputs

- Official Muse SDK commit: `d62b72f8f76b4c18cf9aa64dd3b8781a4f31f7c4`.
- ESP-IDF v6.0.1 commit: `8c19b156084a0753687347cca1f5355782893533`.
- Chip: ESP32-S3 QFN56 revision v0.2; 16 MB Flash; embedded 8 MB AP_3v3 PSRAM. Exact board vendor/model is unconfirmed.
- Overlay: `sdkconfig.voiceshell-s3-test`, copied into official SDK `esp32/devices/`.

The overlay disables LED GPIO drivers, tunnel access, OTA, support uploads, secure boot, Flash encryption, and pairing eFuse authentication. Only the BOOT input on GPIO0 is assigned. No external microphone, display, speaker, or unknown board pin is driven. All generated configuration values must be checked before flashing; the overlay alone is not proof they took effect.

## Private state

Use an isolated ESP-IDF tools directory and a private build directory outside this repository. SDK token defaults, generated `sdkconfig`, binaries, ELF/map files, serial logs, original Flash backups, and any pairing state must remain private. Built firmware contains the SDK token and must not be uploaded as a GitHub artifact.

Build from the official SDK's `esp32` directory with `IDF_TARGET=esp32s3`, a private `SDKCONFIG` path, and defaults in this order: upstream `sdkconfig.defaults`; this board overlay; private token defaults. Do not change partition offsets independently of the official partition table.

## Acceptance gates

1. Read the complete original Flash and verify it against the device. Do not erase Flash or burn eFuses.
2. Finish isolated tool installation, build the pinned SDK, inspect generated security/pin/partition configuration, and inspect image size.
3. Flash the user's designated test board only. Capture boot output privately and check for healthy PSRAM initialization and no panic/reboot loop.
4. Verify actual BLE advertisement, then use Muse developer mode/Add Device and physical BOOT confirmation to test pairing. An SDK token or a successful build is not pairing evidence.
5. Only after pairing, separately validate Linux migration. The later authorized snapshot test succeeded; see the update above. Long-term renewal remains unverified.

Use upstream `tools/muse/monitor.py` only where its reset sequence is appropriate. The first USB-JTAG capture on this board returned DOWNLOAD mode, not a healthy application boot. A physical RESET/EN and a non-resetting serial capture subsequently showed running application heartbeats. Keep DTR/RTS deasserted for that capture. `summarize_boot.py` emits a small credential-free summary from a private raw log; its advertisement field is a firmware report, **not independent radio or phone discovery evidence**.

Never change the production VoiceShell app, the earphone firmware, existing ESP-IDF installation, Bluetooth driver, or machine security settings for this test.

## Current network blocker

The user confirmed that this board's provisioned Wi-Fi is a **phone hotspot**.
The phone app's own cloud connectivity does not prove that tethered clients use
the same route. No conclusion about mobile VPN forwarding has been verified.

The board logged `esp-tls: [sock=54] select() timeout`, `ESP_ERR_HTTP_CONNECT`, and HTTP status 0 during VM lookup. No 401/403 permission denial was observed. The SDK rolled back partial setup and resumed advertising after failure.

Read-only probes to the default `api.muse.ai` endpoint: Windows timed out using both its normal resolution and two temporary public-DNS address candidates; Mac and the Linux server received HTTP 404 at `/`. A 404 proves only endpoint transport reachability, not SDK authentication or account access. The board's actual API origin was not logged, so the default-host comparison is a network clue, not full route equivalence. Different DNS answers alone do not establish DNS poisoning, and the address override did not fix Windows connectivity.

Next options: test a network with working Muse endpoint access, or design an isolated Linux network relay. No global DNS/proxy/routing change or server relay has been deployed. Do not bypass certificate verification or skip cloud validation merely to make the app display pairing success.
