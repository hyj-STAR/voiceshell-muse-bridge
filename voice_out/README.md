# VoiceShell Voice Out Bridge — 实验版

当前能力：Agent 通过受鉴权接口提交文字；独立输出客户端领取文字、确认交付。
Muse 适配器只注册 `voiceshell.output_text`，不注册官方 SDK 默认的 shell 或文件读写工具。
**没有实现 TTS、耳机音频播放、VoiceShell 正式账号绑定或多租户。**

2026-10-03 更新：独立的 [Linux 收发实验](LINUX_MIGRATION_20261003.md) 已完成真实 Muse 账号的两次文字收发，ESP32 应用停止运行时同样成功。该实验使用 `voiceshell.reply`；它不等于本页 `voiceshell.output_text` 队列适配器已通过 Muse 端到端验收。

这是独立的单用户实验，不修改现有客户端、ASR、耳机固件或生产账号数据库。
服务仅监听 `127.0.0.1:18789`，远程开发连接使用 SSH 转发；不直接暴露公网 HTTP。
对外发布前需要接入正式账号授权、撤销机制、TLS、限流和真实耳机验收。

## 开发与测试

```sh
python3 -m unittest discover -s voice_out -p 'test_*.py'
python3 voice_out/bridge.py --state /absolute/private/state
```

初次运行自动生成两份私有密钥，分别只允许生产和领取输出。不要提交、打印或放进 URL。
将服务单元和程序安装到单独目录，使用专属低权限服务账户；不要用 Muse 默认命令执行器运行本组件。

## 开放接口 v1

| 接口 | 授权 | 请求 / 响应 |
|---|---|---|
| `GET /health` | 无，只有回环地址可达 | 实验版本和未实现能力标记 |
| `POST /v1/output/text` | producer Bearer | `{"responseId":"resp-001","text":"你好"}` → HTTP 202 `queued` |
| `GET /v1/output/next` | consumer Bearer | `event` 或 null；含 responseId、text、lease |
| `POST /v1/output/ack` | consumer Bearer | responseId、lease、status：delivered / failed / cancelled |

同一 responseId、同一文字重复提交不新增；不同文字返回 409。responseId 限 ASCII 字母数字、短横线和下划线，最长 80 字符。
`queued` 只表示接收，**不表示已播放**。`delivered` 也不是板端播放完成回执。
租约 60 秒；过期重投，因此输出端也要按 responseId 去重。最多排队 100 条，每条最多 8192 字节。
文字以私有 SQLite 队列暂存，30 分钟后逻辑过期；交付后清空文字列，去重元数据最多保存一天。
这不是端到端加密或磁盘安全擦除承诺。请求和文字不记日志。

## Muse 适配器

使用官方 SDK Linux 固定提交 `d62b72f8f76b4c18cf9aa64dd3b8781a4f31f7c4`。
在隔离 Linux 身份完成真实配对后，设置 `MUSEGADGET_STATE_DIR` 指向该身份的私有目录，再运行：

```sh
python3 muse_adapter.py --producer-key /absolute/private/state/producer.key
```

未配对会拒绝启动。授权迁移的单次凭证快照已在独立实验中验证，但本适配器的持续运行、凭证续期尚未验收；不要同时运行同一身份的两个实例，不要自动搬运未经用户批准的凭证。
Muse 调用上述工具 → 回环文字队列 → 后续 VoiceShell 输出客户端。
还需要补 TTS → PCM16/S16_LE、16 kHz、单声道 → WSS 20ms/640B 分帧，以及实际播放完成回执。
现有服务不是热点网络代理，也不会让未完成的 ESP32 绑定自动成功。
