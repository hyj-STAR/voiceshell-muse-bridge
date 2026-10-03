# Licensing / 许可说明

This repository publishes experimental source and observations for inspection and reference. A project-wide open-source license for original VoiceShell contributions has not yet been selected. Public visibility alone does not grant a general license to redistribute or commercially use those contributions. Contact the maintainer before doing so.

本仓库公开实验代码和记录供查看、参考。VoiceShell 原创部分尚未选定项目级开源许可证；不要把公开可读等同于已授予任意再分发或商业使用许可。

The patch `esp32/serial-chat.patch` contains context from and modifications to the official Muse Gadget SDK, revision `d62b72f8f76b4c18cf9aa64dd3b8781a4f31f7c4`. Upstream copyright belongs to Meta Platforms, Inc. and affiliates; upstream portions retain Apache-2.0 terms. The added experiment changes implement opt-in serial text exchange and correlated reply-tool handling. A copy of the upstream license is included in [UPSTREAM-LICENSE-APACHE-2.0.txt](UPSTREAM-LICENSE-APACHE-2.0.txt). No full SDK, private credentials, firmware binaries or proprietary VoiceShell client are bundled.

SDK access and product integration are separately governed by the upstream [SDK terms](https://gadgets.muse.ai/sdk-terms). We do not claim Muse/Meta sponsorship, endorsement or partnership. See the [upstream source](https://github.com/facebookincubator/muse-gadget-sdk) for its notices and current terms.
