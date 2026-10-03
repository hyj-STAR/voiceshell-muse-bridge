# 我们实际走过的路：ESP32 配对，再到 Linux 直连

记录日期：2026-10-03。这是一次单账号、单块板子的实验，不是一键安装教程。下面区分当时确实跑过的步骤和复现者仍需自行准备的部分。

## 先看结果

ESP32 路径连续完成 3 轮文字收发。随后暂停 ESP32 应用，把机主已授权的设备身份和访问令牌快照私下提供给 Linux，完成 2 次独立连接的文字收发。两次 Linux 测试结束后都关闭了连接，尚未部署 Muse 常驻服务。

我们当时让板子留在下载模式，**没有用物理拔线作为测试条件**。它不运行应用、不转发消息；Linux 独立收发不需要 Windows USB 转发。不要把这个结果写成耳机语音功能已完成。

## 1. 准备和运行不带凭证的测试

```sh
git clone https://github.com/hyj-STAR/voiceshell-muse-bridge.git
cd voiceshell-muse-bridge
python3 -m unittest discover -s esp32 -p 'test_*.py'
python3 -m unittest discover -s voice_out -p 'test_*.py'
```

这只验证本地代码，不会连 Muse、不刷板子、不发消息。首次板端配对仍需要 Muse App、你自己的有效 SDK Token，以及手机附近的受支持蓝牙硬件。

本次板子实测：ESP32-S3、16 MB Flash、8 MB PSRAM、BOOT GPIO0；具体厂商型号未确认。不要把这一份 GPIO、Flash 和 PSRAM 配置套到所有 S3 板子上。

## 2. 固定官方 SDK，检查再打补丁

我们基于官方 SDK，不分发它的含凭证固件。

```sh
git clone https://github.com/facebookincubator/muse-gadget-sdk.git
git -C muse-gadget-sdk checkout d62b72f8f76b4c18cf9aa64dd3b8781a4f31f7c4
git -C muse-gadget-sdk apply --check ../esp32/serial-chat.patch
git -C muse-gadget-sdk apply ../esp32/serial-chat.patch
```

从本仓库根目录执行以上命令。官方源码的新版本可能已经变化，所以先固定版本；`--check` 失败就停，不要硬套。

在独立 ESP-IDF 6.0.1 环境内，按 [板端说明](esp32/README.md) 配置目标 `esp32s3` 和私有构建目录。配置顺序为官方 defaults、板型 overlay、你自己的私有 Token 配置；文字实验另外启用 `CONFIG_HOMEHUB_SERIAL_CHAT=y`。核对分区、实际引脚、镜像尺寸后才烧录指定测试板。已有配对状态时，后续更新只写已核对的应用分区，不清空 NVS。

本仓库不提供通用一键烧录命令：板型尚未普遍验证，错误分区或配置会破坏原有固件。原始 Flash 备份、Token 配置、生成固件都留在仓库外。这个实验 overlay 没有启用 Secure Boot/Flash 加密，不适合作为量产安全配置，也不要对已有安全配置的设备照搬。

## 3. 在 Muse App 配对，不在电脑蓝牙设置里配对

1. 先让板子正常启动。我们曾读到 `DOWNLOAD`，只短按 RESET/EN 后才运行应用；不要一直按 BOOT。
2. Muse App 更新后出现了 Add Device。App 发现 MuseGadget 后，按提示用 BOOT 确认并配网。
3. 分别检查“手机发现设备”“加入 Wi-Fi”“云端连接”。这三件事不是同一个成功条件。

最初板子已加入热点，但云端 VM 查询出现 socket timeout、HTTP status 0。没有收到 401/403，所以不能据此认定 Token 过期。手机 App 能连，不说明热点下的板子也走同一路径。后来通过可用的 Windows 热点及代理连接路径完成云端接入；本仓库不包含当时个人网络配置，也不宣称普通热点自动共享手机代理。

复现时，先核验你的板子网络到服务端的实际连通性；不要关闭 TLS 校验，也不要反复更换 Token 掩盖网络问题。

## 4. 先确认发送，再确认回复回到设备

安装 `pyserial` 到自己的虚拟环境，进入本仓库根目录。以下 COM7 只是当时的端口，换成你的实际端口。

```sh
python3 esp32/serial_chat.py --port COM7 --status
python3 esp32/serial_chat.py --port COM7 --tool-reply --message '请回复：VoiceShell 已连接'
```

第二条命令会向自己的 Muse 发送一条真实消息。成功标准是收到同一轮编号的回复，不是只看到 HTTP 200。超时后不要自动重发：消息可能已经送达。

我们遇到的关键坑：`POST /chat/stream` 接受了消息，手机也显示了回答，但设备的 `GET /chat/history` 返回 403：`path not allowed for device token`。最终使用自定义 `voiceshell.reply` 工具，由 Muse 调用后把文字送回设备。每轮有唯一关联编号，拒绝不匹配的回复。

这依赖模型调用工具，不是读聊天历史，也不是逐字流式输出。[板端代码与验证细节](esp32/SERIAL_CHAT.md) · [3 轮实测记录](esp32/TEST_REPORT_20261003.md)

## 5. Linux 独立收发实验

在 Linux 的独立虚拟环境安装固定版本官方 SDK：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ./muse-gadget-sdk/linux
```

前提是机主已经授权配对，且自行安全准备了仓库之外的 JSON 状态文件，字段为 `mac`、`access_token`，可选 `api_url_v2`、`noise_host`。权限应为仅机主可读。不在 Issue 上传它，也不要把秘密直接放进命令行。

**本仓库没有自动导出配对凭证的工具；尚未完成初始配对、没有授权状态文件的读者，不能直接跑这一段。** 此次使用的是访问令牌快照，没有导出刷新令牌。未来续期与受支持的迁移方式仍需验证。

先停止 ESP32 应用，避免同一身份双端在线。以下命令会建立两次连接，并各发一条测试消息：

```sh
.venv/bin/python voice_out/linux_roundtrip_probe.py /absolute/private/pairing.json
```

观察 VM lookup 200 → 注册成功 → 发送接受 → 对应编号回复 → `SERVER_ONLY_TWO_SESSIONS_PASSED`。任一步失败都不算完成。这个探针只注册文字回复工具，不注册默认 shell、文件、OTA 工具；不是常驻服务。

当次两次会话耗时 19.4 秒、6.6 秒，只是样本，不是性能承诺。[完整实验边界](voice_out/LINUX_MIGRATION_20261003.md)

## 踩坑速查

| 现象 | 当时查到什么 | 可参考的处理 |
| --- | --- | --- |
| App 没有添加设备入口 | 更新 App 后入口出现 | 先确认 App 版本，再查广播 |
| Mac 报广播成功，手机搜不到 | OS 回调不等于发现成功 | 用手机真实发现作判据 |
| Windows 支持外设模式但搜不到 | GATT Aborted；重启、桌面会话、包身份仍没修复 | 保留失败记录；不能泛化成所有 Windows 不支持 |
| 烧录后没有正常启动 | 板子仍在 DOWNLOAD | 只短按 RESET/EN，检查串口控制线 |
| Wi-Fi 已连，App 仍在等待 | VM 查询超时、HTTP 0 | 分层查网络，不直接归因 Token |
| 消息发出，设备收不到回复 | 历史接口 403 | 使用授权设备工具回传，不绕过历史权限 |
| Linux 跑通就认为可以发布量产 | 仅两次短会话成功 | 补续期、掉线恢复、并发和持续运行测试 |

[更详细的 Mac/Windows 历史调查](COMPATIBILITY_HISTORY.md)保留了失败尝试。历史文件里的“未配对”是当时的状态，不是最新结论。

## 还需要大家一起补的部分

常驻进程和安全续期、撤销设备、统一客户端接口、多用户隔离、断网恢复，以及耳机 ASR → Muse → TTS → 播放。`voice_out/bridge.py` 的队列测试使用过合成文字，不能拿它替代真实 Muse 或耳机验收。

提交复现结果时，请写板型、SDK 版本、在哪一步成功或失败，以及脱敏后的状态。不要提交 Token、Wi-Fi 密码、账号截图或原始 Flash。可读的公开参考源码与商业使用许可是两件事，见 [许可说明](LICENSING.md)。
