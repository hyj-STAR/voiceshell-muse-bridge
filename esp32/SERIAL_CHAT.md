# Device-originated text experiment

This experiment targets **VoiceShell → paired ESP32 → Muse → text reply**.
It is separate from the existing `device.health` command, which runs in the
opposite direction. It is not an audio implementation or a released product.

## Implementation

`serial-chat.patch` applies to the Muse Gadget SDK commit
`d62b72f8f76b4c18cf9aa64dd3b8781a4f31f7c4`.
It adds an opt-in `CONFIG_HOMEHUB_SERIAL_CHAT` for a headless ESP32-S3 with
PSRAM. It reuses the existing authenticated Noise connection and the official
`POST /chat/stream` request shape. It does not export device credentials.

The bridge accepts only USB status, one-line text submission, and bounded
chat-history reads, and a correlated text-only `voiceshell.reply` device tool.
The tool accepts at most 1024 UTF-8 bytes for the currently pending USB request;
unmatched and conflicting replies are rejected. No shell execution, setup changes, arbitrary URLs, OTA,
microphone, display, GPIO remapping, or LAN discovery are added.

Host helper (requires pyserial):

```sh
python serial_chat.py --port COM7 --status
python serial_chat.py --port COM7 --send-only --message 'Please reply: VoiceShell connected'
python serial_chat.py --port COM7 --tool-reply --message 'Please reply: VoiceShell connected'
python -m unittest discover -p 'test_serial_chat.py'
```

The helper preserves DTR/RTS, posts a message once, and looks for a completed
assistant reply associated with that new message. A timeout never resends the
message automatically; delivery can be unknown and must be inspected.
History rows used to establish the sequence cursor are not printed.
Use `--send-only` on the tested gadget: its paired session accepts message
submission but returns HTTP 403 for history reads. View replies in the Muse
main chat. Omitting this flag tests history-based reply collection, which is
not currently available on this device; it fails before posting.
`--tool-reply` instead asks Muse to call the advertised reply tool. This is
model-mediated tool delivery, not unrestricted access to chat history, not
streaming, and not guaranteed to be invoked on every turn. It polls the
board's in-memory reply buffer, never the blocked history endpoint.

## Firmware safeguards

Enable the opt-in flag in the existing board-specific build configuration.
Do not substitute a display-board overlay or change flash layout. Before
flashing, verify board identity, SDK revision, application size and partition
offset against that particular device. Preserve the previous private app
image and configuration. Write only the existing application slot; never
erase flash or overwrite NVS to enable this feature.

SDK tokens are embedded in built binaries. Neither binaries, generated
sdkconfig files, pairing storage, private logs nor Wi-Fi credentials belong
in this repository. The SDK's token terms are separate from its source-code
license; this remains a personal prototype, not authorization to distribute
a commercial Muse-enabled device.

## Verification status

Client unit tests: 10 passing. Relevant upstream diagnostic-log and serial-chat
tests: 17 passing. The complete host suite on the Mac is blocked by missing
CMake and the managed cJSON source; this is not a full-suite pass.
On 2026-10-03, ESP-IDF 6.0.1 built the firmware successfully (1,314,816 bytes
in a 2,097,152-byte app slot). The application-only flash was verified; NVS
was not written. Boot showed no panic, retained setup, Wi-Fi up and Muse
WebSocket up. The USB status command reported connected.

A single device-originated test message was accepted by `POST /chat/stream`,
returning a nonempty message ID and `channel: main`. This verifies submission,
not assistant completion or any downstream action. `GET /chat/history`
returned HTTP 403 with `path not allowed for device token`. History retrieval
remains blocked. The first device-tool test returned the requested Chinese
reply through the board to the USB host, with the expected correlation ID.
This verifies a text round trip using device tool invocation;
do not claim headset/ASR/TTS integration. The tested path still
depends on the Windows USB host and its working hotspot/proxy connection.

Three consecutive live requests completed through the device-tool path:
Chinese acknowledgement, a short arithmetic answer, and a full Chinese
sentence describing the prototype limitation. Each used a fresh correlation
ID and a single POST. Rounds two and three took 5.7 s and 3.5 s measured around
the entire host-client process, not a latency benchmark. First-round timing
was not recorded. No streaming, disconnection recovery, concurrency, soak,
or headset audio acceptance is claimed.
