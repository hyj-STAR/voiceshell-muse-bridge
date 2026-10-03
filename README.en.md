<div align="center">

# VoiceShell Muse Bridge

[![GitHub stars](https://img.shields.io/github/stars/hyj-STAR/voiceshell-muse-bridge?style=flat)](https://github.com/hyj-STAR/voiceshell-muse-bridge/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/hyj-STAR/voiceshell-muse-bridge?style=flat)](https://github.com/hyj-STAR/voiceshell-muse-bridge/forks)

[Reproduction walkthrough and pitfalls (中文)](WALKTHROUGH.md) · [Contributing](CONTRIBUTING.md) · [Licensing](LICENSING.md)

### Pair on a board. Run the connection on your server.

**A path from your devices to your Muse, without an ESP32 in every message hop.**

[简体中文](README.md) · [English](README.en.md)

![Stage: experimental](https://img.shields.io/badge/stage-experimental-f4b942)
![Transport: official SDK](https://img.shields.io/badge/transport-official_Muse_SDK-4656a5)
![Scope: text roundtrip](https://img.shields.io/badge/verified-text_roundtrip-198a75)

[Evidence](#evidence) · [Get started](#get-started) · [Hardware and roadmap](#hardware-and-roadmap) · [Collaborate](#collaborate)

<img src="assets/bridge-hero.svg" alt="ESP32 for initial pairing, Linux for independent text round trips to Muse" width="100%"/>

</div>

## Why a bridge?

You already have computers, wearables and connected devices. We want them to reach your own agent without each one needing its own dedicated Muse gadget in the message path.

Our experiment starts with user-authorized ESP32 pairing, then moves that authorized connection to Linux. **The key step worked: with the ESP32 application stopped, Linux independently sent messages and received Muse's text replies.**

The broader goal is to connect other clients through the bridge. Their APIs, authorization and adapters are still to be built. Internet access alone does not make a device plug-and-play.

## Evidence

**2026-10-03 · Real Muse account · Physical ESP32-S3 · Separate Linux server**

| Verified | Result | Evidence |
| --- | --- | --- |
| ESP32 → Muse → ESP32 → USB host | 3 consecutive text round trips | [Hardware test report](esp32/TEST_REPORT_20261003.md) |
| Linux → Muse → Linux, ESP32 application stopped | 2 independent sessions passed | [Migration report](voice_out/LINUX_MIGRATION_20261003.md) |
| Reply correlation | Fresh ID per request; matching replies only | [Probe source](voice_out/linux_roundtrip_probe.py) |
| Official SDK reuse | Connection, registration and message submission | [Upstream Linux SDK](https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux) |

The two Linux replies were the requested Chinese confirmation strings, “第1轮：Linux直连回传成功” and “第2轮：Linux直连回传成功”. These prove text delivery, not arbitrary task execution. Sessions closed normally after testing; **this is not an always-on deployment**. Observed durations were 19.4 s and 6.6 s, not a benchmark.

<details>
<summary><b>View the real source and test-report screenshots</b></summary>

<img src="assets/linux-send-receive-code.jpg" alt="Actual committed Linux send and receive code" width="100%"/>

Source shows implementation, not execution. The screenshot below is our own test report, not independent certification or a raw terminal capture.

<img src="assets/linux-test-report.jpg" alt="Our Linux migration test report on GitHub" width="100%"/>

Phone screenshots and a continuous demo recording are not yet included. No synthetic chat images stand in for live evidence.

</details>

## Built on the official examples

- **Upstream:** pairing, encrypted transport, device registration and `POST /chat/stream` submission.
- **Our addition:** the text-only `voiceshell.reply` tool, per-request correlation and an independent Linux round-trip probe.
- **Reply path:** Muse invokes the device tool with the answer. The device token received 403 on chat history; this implementation does not bypass that restriction.

Delivery depends on Muse invoking the tool correctly. It is neither streaming output nor unrestricted chat-history access. This is an independent project, **not an announced partnership with Muse or Meta**.

## Get started

Developer research code, not a one-command installer. Choose the experiment you want to reproduce:

| Task | Entry point |
| --- | --- |
| Understand the tested board and initial pairing | [ESP32 setup](esp32/README.md) |
| Test USB text on an already-paired ESP32 | [Serial bridge](esp32/SERIAL_CHAT.md) |
| Review independent Linux operation and prerequisites | [Linux migration](voice_out/LINUX_MIGRATION_20261003.md) |
| Build a text-output client | [Single-owner output queue](voice_out/README.md) |
| Inspect previous Mac/Windows BLE attempts | [Compatibility history](COMPATIBILITY_HISTORY.md) |

Credential-free tests, from the repository root:

```sh
python3 -m unittest discover -s esp32 -p 'test_serial_chat.py'
python3 -m unittest discover -s voice_out -p 'test_*.py'
```

The official Linux setup needs Python 3.9+, an SDK token, the Muse app and user-approved device pairing. Our tested SDK revision is `d62b72f8f76b4c18cf9aa64dd3b8781a4f31f7c4`.

**Do not run the same identity on ESP32 and Linux simultaneously.** The successful authorized migration test does not establish portability of every credential or indefinite token renewal. No automatic credential-extraction installer is provided.

## Hardware and roadmap

| Component | Role | Status |
| --- | --- | --- |
| ESP32-S3, tested with 16 MB flash / 8 MB PSRAM | Initial pairing and board-side tests | Verified on this board, not every ESP32 variant |
| Linux server | Muse text communication without ESP32 forwarding | Two independent sessions passed |
| VoiceShell AC7912 headset prototype | Target wearable input/output device | Muse audio path not verified in this experiment |
| Phones, desktop apps and other connected devices | Future bridge clients | API, authorization and adapters pending |

- [x] Real ESP32 pairing and text replies
- [x] Independent Linux text round trips and fresh-session verification
- [ ] Restricted persistent service, token renewal and revocation
- [ ] Stable client API and multi-user isolation
- [ ] Production VoiceShell client integration
- [ ] Headset capture → ASR → Muse → TTS → playback
- [ ] Reconnect, cancellation, soak tests and more device adapters

## About VoiceShell

**Speak Freely. Stay Private.**

VoiceShell（声壳）is building wearable voice-input hardware and companion software for quieter, less conspicuous interaction with your own agents. The bridge is part of that direction.

Low-volume input is a development goal; fully silent input is not a verified capability of this prototype. The Muse experiment sends text to Muse's service. It is **not an all-local or offline feature**.

## Collaborate

We welcome hardware builders, agent/software teams and developers working on device adapters, voice interaction and real-world testing.

Reach the VoiceShell team through [our GitHub profile](https://github.com/hyj-STAR) or [open a discussion issue](https://github.com/hyj-STAR/voiceshell-muse-bridge/issues/new). Tell us what you are building, your intended interaction and the interfaces you already have.

Public WeChat/contact-group QR codes will be added after the team supplies the approved images. Never share account credentials or tokens in issues.

## Privacy and permissions

The Linux experiment advertises only the text-reply tool, not the SDK's default shell/file tools or OTA. Tokens, pairing state and credential-bearing firmware binaries stay outside Git.

Research source is not commercial access approval. Review the [Muse Gadget SDK Terms](https://gadgets.muse.ai/sdk-terms) and [licensing notes](LICENSING.md). This standalone public research repository excludes the VoiceShell client and private repository history. Public visibility does not mean all files have an open-source license.

## Star History

Star the project if the experiments help you, or share a reproduction report. This chart uses real GitHub data; a new repository may not have a curve yet.

[![Star History Chart](https://api.star-history.com/svg?repos=hyj-STAR/voiceshell-muse-bridge&type=Date)](https://www.star-history.com/#hyj-STAR/voiceshell-muse-bridge&Date)

Powered by [Star History](https://github.com/star-history/star-history). If the image is unavailable, follow the link or use the GitHub star counter above.

---

Built by **VoiceShell（声壳）** · Based on the [official Muse Gadget SDK](https://github.com/facebookincubator/muse-gadget-sdk)

Independent experiment. Real text round trips. More devices next.
