# Linux standalone migration experiment

On 2026-10-03, the owner's already-authorized ESP32 device identity and an
access-token snapshot were supplied privately to the isolated Linux SDK
test environment. No token is in this repository. Refresh tokens were not
exported or rotated. This was not a new account authorization or a bypass
of the device's chat-history permission boundary.

During both tests, the ESP32 was held in download mode, with its application
and Muse connection stopped. No flash data was erased or written. The test
ran on the remote Linux server, not through Windows USB or the ESP32.

| Test | Result |
| --- | --- |
| Device VM lookup | HTTP 200 in both sessions |
| Linux device registration | Passed in both sessions |
| Device-originated message | HTTP 200 in both sessions |
| Correlated reply tool invocation | Returned to Linux in both sessions |
| Session one reply | 第1轮：Linux直连回传成功 |
| Session two reply after a fresh connection | 第2轮：Linux直连回传成功 |
| Time from session start through reply | 19.4 s, 6.6 s; not a benchmark |

The official Linux SDK handles the encrypted connection and registration
as `platform: linux`, `device_family: homehub`. Only `voiceshell.reply` is
advertised. No default shell, file read/write, OTA or LAN-discovery executor
is exposed. Each test POST occurs once, with a fresh reply correlation ID.

Conclusion: this identity was accepted on Linux, and ESP32 forwarding is
not required for this tested text round trip. The two test sessions closed
normally afterward; this is NOT an always-on service deployment. The ESP32
remains paused in download mode and can be unplugged. To return to the old
hardware demo, stop any Linux session first, then reset the board normally.
Do not run both implementations with the same identity at once.

Remaining: persistent restricted service, secure token refresh/lifecycle,
client integration, disconnect recovery/soak testing, multi-user isolation,
and the headset audio path. A successful access-token snapshot test does
not establish indefinite operation or supported commercial migration.

`linux_roundtrip_probe.py` takes a private JSON file containing `mac`,
`access_token` and optional `api_url_v2`/`noise_host`. Use only the owner's
authorized state, with strict file permissions. Never commit that file or
raw flash backups. It intentionally has no automatic token refresh, no
pairing reset, no public listener and no default system-command executor.
