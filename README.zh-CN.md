<div align="center">

# VoiceShell Muse Bridge

### 一块 ESP32，完成首次绑定。接下来的连接，交给服务器。

**让你的设备连接自己的 Muse，而不必一直依赖那块开发板。**

[English](README.md) · [简体中文](README.zh-CN.md)

[![GitHub stars](https://img.shields.io/github/stars/hyj-STAR/voiceshell-muse-bridge?style=flat)](https://github.com/hyj-STAR/voiceshell-muse-bridge/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/hyj-STAR/voiceshell-muse-bridge?style=flat)](https://github.com/hyj-STAR/voiceshell-muse-bridge/forks)

[![Stage: experimental](https://img.shields.io/badge/stage-experimental-f4b942)](#硬件与路线图)
[![Transport: official SDK](https://img.shields.io/badge/transport-official_Muse_SDK-4656a5)](#基于官方例程)
[![Scope: text roundtrip](https://img.shields.io/badge/verified-text_roundtrip-198a75)](#实测证据)

[实测证据](#实测证据) · [开始实验](#开始实验) · [硬件与路线图](#硬件与路线图) · [合作交流](#合作交流)

<img src="assets/bridge-hero.svg" alt="ESP32 完成首次配对，Linux Bridge 独立与 Muse 收发文字" width="100%"/>

</div>

## 为什么做这个

我们在做 VoiceShell（声壳），希望让人与自己的 Agent 交流得更低声、更不显眼。看到 Muse Gadgets 后，我们最先想到的是：能不能把它接到我们正在做的设备上？

我们的耳机不是 ESP32。于是问题变得更具体：**能不能先用 ESP32 完成配对，再让自己的 Linux 服务器负责后面的消息收发？** 如果这一步成立，自己的软件和硬件就有了继续做适配的地方，不必让每条消息都经过那块开发板。

我们顺着官方 SDK 试了一遍。Mac 报告广播成功，手机却搜不到；换到 Windows，蓝牙能力检测通过，真正发布 GATT 服务时还是失败。后来换上 ESP32-S3，手机终于看见了设备，又卡在了配网之后。

最后走通了两段：ESP32 连续完成三轮文字收发；停止板子上的应用后，Linux 又独立完成两次连接和文字回传。这里分享的，就是这条实际走过的路。接更多终端的接口、授权和适配还要继续做。

## 配网这件事，比我们一开始想的多了几层

### 手机看见设备，还不算配对完成

最初 Muse App 没有显示添加设备入口，更新之后才出现。再往后，板子被发现、按 BOOT 确认、加入 Wi-Fi，每一步都得单独看。手机能搜到，只说明蓝牙发现这一步过去了。

我们也遇到过烧录成功却没有正常启动：串口显示的是 DOWNLOAD 下载模式。只短按 RESET/EN 后，板子才开始运行应用。这个时候继续在 App 里刷新，解决不了启动状态的问题。

### Wi-Fi 已经连上，为什么 App 还在转？

当时最容易让人误判的就是这里。板子已经加入热点，App 仍然提示正在连接，日志里则是 VM 查询超时、HTTP 状态 0。

我们也怀疑过 Token。但当时没有拿到 401 或 403 这样的鉴权拒绝，连有效的 HTTP 响应都没有。仅凭“连不上”，还不能判断是凭证过期。

后来通过可用的 Windows 热点和代理路径，完成了云端连接。这让我们在排查时把两个问题分开：**手机自己能访问 Muse，和接在热点下面的板子能访问 Muse，不是一回事。** 普通热点不一定转发手机上的代理，换 DNS 也不是每次都有效。

如果你卡在同一步，先看板子是否正常启动、手机是否发现它、Wi-Fi 是否加入成功，再检查云端连接。不要一边反复换 Token，一边把真正的网络错误盖过去。更详细的观察和操作顺序放在[完整流程](WALKTHROUGH.md)里，个人网络配置和凭证没有上传。

### 发出去了，回复为什么没回来？

联网后还有一个坑：消息发送成功，手机上也能看见 Muse 回答，但设备读聊天历史时返回 403，明确写着 `path not allowed for device token`。

我们最后加了 `voiceshell.reply` 这个文字回传工具，让 Muse 调用它，把回答送回来。每轮请求带一个独立编号，只接收对应的回复。这样跑通了文字往返，但它依赖模型调用工具，还不是逐字流式输出。

这些失败尝试也留在了[兼容性记录](COMPATIBILITY_HISTORY.md)里。希望你复现时，能少花一点时间在我们已经走过的弯路上。

## 实测证据

**2026-10-03 · 真实 Muse 账号 · 真实 ESP32-S3 · 独立 Linux 服务器**

| 已验证 | 结果 | 可查看的记录 |
| --- | --- | --- |
| ESP32 → Muse → ESP32 → 电脑 | 连续 3 轮文字收发成功 | [硬件测试记录](esp32/TEST_REPORT_20261003.md) |
| Linux → Muse → Linux，ESP32 应用已停止 | 2 次独立会话均完成收发 | [迁移测试记录](voice_out/LINUX_MIGRATION_20261003.md) |
| 回复关联 | 为每轮生成编号，仅接受对应回复 | [实际测试代码](voice_out/linux_roundtrip_probe.py) |
| 官方例程复用 | 使用官方 Linux SDK 的连接、注册、发送机制 | [官方 SDK](https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux) |

> “第1轮：Linux直连回传成功”
>
> “第2轮：Linux直连回传成功”

以上是当次测试指定并收到的确认文本，不代表通用任务执行能力。测试结束后连接正常关闭；**还不是全天在线服务**。两次 Linux 会话耗时 19.4 秒、6.6 秒，仅为当次样本，不是性能指标。

<details>
<summary><b>查看真实 GitHub 代码与实测报告截图</b></summary>

<img src="assets/linux-send-receive-code.jpg" alt="已提交的 Linux 消息发送及回传代码截图" width="100%"/>

代码截图用于展示实现；下图是我们自己的实测报告，不是第三方认证或原始终端日志。

<img src="assets/linux-test-report.jpg" alt="Linux 独立收发实测报告截图" width="100%"/>

连续录屏尚未补齐。没有使用合成对话图代替实测画面。

</details>

### 手机上实际看到了什么

下面是测试者提供的原始截图，没有改写对话：设备列表出现了 **VoiceShell Linux Bridge Test**；对话里能看到两轮指定测试消息，以及 Muse 对第二轮的确认。

<img src="assets/muse-device-list.jpg" alt="Muse 设备列表出现 VoiceShell Linux Bridge Test" width="280"/>
<img src="assets/muse-chat-test.jpg" alt="两轮测试消息与 Muse 的第二轮确认" width="360"/>

单看聊天截图，不能证明 Linux 已收到工具回传，也不能证明 ESP32 当时停机，需要结合[服务器实验记录](voice_out/LINUX_MIGRATION_20261003.md)看。图中的 correlation 是每轮测试编号，不是登录令牌。设备页还保留了官方开发者模式提示：社区设备未经 Meta 验证，并会取得广泛的 Agent 访问权限；我们只开放文字回传工具，不代表这个账号级授权提示可以忽略。

## 基于官方例程

我们没有重新发明 Muse 的连接协议：

- **官方 SDK**：设备配对、加密连接、设备注册，以及 `POST /chat/stream` 发送消息。
- **我们的扩展**：文字回复工具 `voiceshell.reply`、每轮请求编号匹配，以及服务器独立收发验证。
- **这次走通的方法**：Muse 调用回复工具，把文字送回 Bridge。设备凭证读取聊天历史返回 403，我们没有绕过它。

回复回传依赖 Muse 正确调用设备工具，不是聊天历史访问，也不是实时流式输出。此项目独立开发，**不代表与 Muse 或 Meta 已建立官方合作**。

## 开始实验

**先看：[从配对到 Linux 的真实流程与踩坑记录](WALKTHROUGH.md)。** 包括实验顺序、成功判据、失败现象、可运行命令和仍然缺少的部分。

```sh
git clone https://github.com/hyj-STAR/voiceshell-muse-bridge.git
cd voiceshell-muse-bridge
```

这是开发者研究代码，不是一键安装包。先选要验证的路径：

| 你想做什么 | 从这里开始 |
| --- | --- |
| 了解 ESP32 的首次配对和板级要求 | [ESP32 实验说明](esp32/README.md) |
| 在已配对 ESP32 上测试文字收发 | [USB 文字桥接说明](esp32/SERIAL_CHAT.md) |
| 复核 Linux 不依赖板子的收发实验 | [Linux 迁移记录与前提](voice_out/LINUX_MIGRATION_20261003.md) |
| 为自己的输出端开发适配 | [单用户文字输出队列](voice_out/README.md) |
| 查看之前的 Mac / Windows 蓝牙尝试 | [历史兼容性日志](COMPATIBILITY_HISTORY.md) |

先跑不需要设备凭证的测试。在仓库根目录运行：

```sh
python3 -m unittest discover -s esp32 -p 'test_serial_chat.py'
python3 -m unittest discover -s voice_out -p 'test_*.py'
```

Linux 官方流程要求 Python 3.9+、有效 SDK Token、Muse App 和经用户批准的设备绑定。我们测试用 SDK 固定版本为 `d62b72f8f76b4c18cf9aa64dd3b8781a4f31f7c4`。

**不要把同一个设备身份同时运行在 ESP32 和 Linux 上。** 授权迁移实验的成功，不等于任何设备凭证都可迁移，也不证明它可以无限期续期。没有提供自动提取凭证的一键脚本。

## 硬件与路线图

| 部件 | 在项目中的位置 | 当前状态 |
| --- | --- | --- |
| ESP32-S3（本次测试：16 MB Flash / 8 MB PSRAM） | 首次配对与板端验证 | 已验证；并非所有 ESP32 型号均已测试 |
| Linux 服务器 | 不经 ESP32 转发的 Muse 文字收发 | 2 次独立会话通过 |
| VoiceShell AC7912 耳机原型 | 随身输入和音频反馈的目标终端 | 本次未验证 Muse 语音闭环 |
| 手机、桌面软件和其他联网设备 | 通过 Bridge 接入的目标客户端 | 统一接口、授权与适配待完成 |

- [x] ESP32 真实配对与文字回传
- [x] Linux 独立文字收发与重新建连验证
- [ ] 受限权限的常驻服务、凭证续期与撤销
- [ ] 稳定的客户端接口与多用户隔离
- [ ] VoiceShell 正式客户端接入
- [ ] 耳机录音 → ASR → Muse → TTS → 播放
- [ ] 掉线恢复、取消、持续运行和更多设备适配

## VoiceShell（声壳）

**Speak Freely. Stay Private.**

我们在做随身语音输入硬件和配套软件，希望在办公等场景里，让人与自己的 Agent 交流得更低声、更不显眼。Bridge 是这个方向的一部分。

低声输入是我们的研发方向；完全无声的输入尚不是此原型的已验证能力。本次 Muse 测试只传文字，**文字会发送到 Muse 的服务**，不能把这一功能描述为全本地、不出网。

## 合作交流

**欢迎硬件团队、Agent／软件团队和开发者一起做设备适配、语音交互与真实场景测试。**

想和 VoiceShell 团队讨论合作，可以[提交交流议题](https://github.com/hyj-STAR/voiceshell-muse-bridge/issues/new)，或查看我们的 [GitHub 主页](https://github.com/hyj-STAR)。复现反馈请参考 [贡献说明](CONTRIBUTING.md)。

介绍一下你正在做的设备、想接入的场景，以及已有的接口，我们可以从一个可验证的小演示开始。

### 小红书交流群

用小红书扫码加入 **muse gadgets 交流群 (1)**，一起交流复现和设备适配。这是社区交流群，不是 Muse／Meta 官方支持群。

<img src="assets/xiaohongshu-group.jpg" alt="小红书群二维码，图示有效期至 2026-10-31" width="300"/>

图片标注有效期至 **2026 年 10 月 31 日**；尚未独立验证扫码入群。如果过期，可在 Issue 中索取更新邀请。微信入口和小红书个人主页待补；请勿在 Issue 或群聊里发送令牌、账号凭证或私人资料。

## 隐私与授权边界

本次 Linux 实验只注册文字回传工具，不开放默认 shell、文件读写或 OTA。SDK Token、设备凭证、配对存储和含 Token 的固件二进制不进入仓库。

实验代码不等于商业接入授权。使用前阅读 [Muse Gadget SDK Terms](https://gadgets.muse.ai/sdk-terms) 和[许可说明](LICENSING.md)。这是独立公开的实验仓库，不包含 VoiceShell 客户端或私人仓库历史；公开可读不等于整个项目已采用开源许可证。

## Star History

如果这些实验对你有帮助，欢迎 Star，或带着你的硬件复现结果来交流。这里显示真实 GitHub 数据，新仓库暂时没有曲线也是正常的。

[![Star History Chart](https://api.star-history.com/svg?repos=hyj-STAR/voiceshell-muse-bridge&type=Date)](https://www.star-history.com/#hyj-STAR/voiceshell-muse-bridge&Date)

图表由 [Star History](https://github.com/star-history/star-history) 提供；如果图片暂未生成，可点击查看，或直接查看上方 GitHub Star 数。

---

Built by **VoiceShell（声壳）** · Based on the [official Muse Gadget SDK](https://github.com/facebookincubator/muse-gadget-sdk)

Independent experiment. Real text round trips. More devices next.
