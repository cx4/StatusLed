# pc_esp32_control 灯语与 Hook 映射

本文说明 `pc_esp32_control` 使用的红、黄、绿三色信号灯语言，以及 Codex、Claude Code hook 事件到灯效的映射。当前项目的硬件出口是 `ESP32-C3 Super Mini + RGB LED`，PC 端通过 HTTP、串口或 BLE 向 ESP32-C3 发送状态命令。

灯语刻意保持简单：当前灯效直接表示当前状态。只要 Codex 或 Claude Code 正在工作、等待授权、需要关注或遇到阻塞，灯效就会持续运行，直到新的 hook 事件改变状态。会话结束时会短暂闪一下绿灯作为完成提示，然后恢复到当前聚合状态。

注意：当前代码里 `permission` 使用黄灯闪烁，`blocked` 使用红灯闪烁。

## 状态语义

| 灯效 | 含义 | 你需要做什么 |
| --- | --- | --- |
| 白灯快速双闪，长间隔 | agent 空闲或待命 | 不需要处理 |
| 红、黄、绿柔和循环 | agent 已收到任务，正在思考或调度工作 | 等待 |
| 绿灯柔和脉冲 | agent 正在执行工具、读写文件、运行命令或测试 | 等待 |
| 黄灯闪烁 | agent 需要你阅读、确认、授权或继续 | 查看 Codex/Claude Code |
| 红灯闪烁 | agent 阻塞、失败或无法继续 | 立即查看并处理 |
| 全灭 | 手动关闭灯光 | 不需要处理 |

## 信号名称

CLI 暴露稳定的信号名称，供命令行、hook 和其他 agent 调用。

| 信号名 | 灯效 | 含义 |
| --- | --- | --- |
| `idle` | 白灯快速双闪，长间隔 | agent 空闲 |
| `thinking` | 红、黄、绿柔和循环 | agent 已收到任务，正在思考或规划 |
| `working` | 绿灯柔和脉冲 | agent 正在执行工具、读写文件、运行命令或测试 |
| `tool_done` | 红、黄、绿柔和循环 | 一次工具调用完成，但 agent 仍在工作流中 |
| `attention` | 黄灯闪烁 | agent 希望你阅读结果或继续回复 |
| `done` | 黄灯闪烁 | 当前任务完成，建议查看最终答复 |
| `permission` | 黄灯闪烁 | Codex 或 Claude Code 请求授权或需要明确批准 |
| `blocked` | 红灯闪烁 | agent 无法继续，需要人工介入 |
| `session_start` | 绿灯常亮 | 会话开始并处于空闲态 |
| `session_end` | 短暂绿灯完成提示，然后恢复聚合状态 | 会话结束 |
| `session_done` | 短暂绿灯闪烁 | 内部使用的单会话完成提示 |
| `off` | 全灭 | 清除并关闭所有灯光 |

## Codex Hook 映射

| Codex 事件 | 信号名 | 灯效 |
| --- | --- | --- |
| `SessionStart` | `session_start` | 绿灯常亮 |
| `UserPromptSubmit` | `thinking` | 红、黄、绿柔和循环 |
| `PreToolUse` | `working` | 绿灯柔和脉冲 |
| `PostToolUse` | `tool_done` | 红、黄、绿柔和循环 |
| `PermissionRequest` | `permission` | 黄灯闪烁 |
| `Stop` | `turn_end` | 清除当前会话的非紧急工作状态 |
| `SessionEnd` | `session_end` | 短暂完成提示后恢复聚合状态 |

`turn_end` 是 hook 专用控制状态，不是公开灯效。它会移除该会话的非紧急工作状态，但保留已有的 `permission` 或 `blocked` 告警。

如果 hook stdin 的 JSON 载荷包含 `signal`、`signal_name` 或 `lamp_signal`，且值是本项目支持的信号名，会覆盖事件默认映射。载荷中出现 `status`、`state`、`error`、`failure`、`exception`、非零 `exit_status` 等失败标记时，会映射为 `blocked`。

## Claude Code Hook 映射

| Claude Code 事件 | 信号名 | 灯效 |
| --- | --- | --- |
| `SessionStart` | `session_start` | 绿灯常亮 |
| `UserPromptSubmit` | `thinking` | 红、黄、绿柔和循环 |
| `PreToolUse` | `working` | 绿灯柔和脉冲 |
| `PostToolUse` | `tool_done` | 红、黄、绿柔和循环 |
| `PostToolUseFailure` | `blocked` | 红灯闪烁 |
| `PreCompact` | `working` | 绿灯柔和脉冲 |
| `SubagentStart` | `working` | 绿灯柔和脉冲 |
| `SubagentStop` | `tool_done` | 红、黄、绿柔和循环 |
| `PermissionRequest` | `permission` | 黄灯闪烁 |
| `Notification` | `attention` | 黄灯闪烁 |
| `Stop` | `turn_end` | 清除当前会话的非紧急工作状态 |
| `SessionEnd` | `session_end` | 短暂完成提示后恢复聚合状态 |

如果 Claude Code 的 `Stop` 载荷里 `stop_reason` 是 `max_tokens` 或 `error`，当前适配器会映射为 `blocked`，而不是清除状态。

## 聚合优先级

Hook 状态是会话感知的。每个会话都会保存自己的最新信号，然后物理灯显示优先级最高的聚合状态：

```text
blocked > permission > attention/done > thinking/working/tool_done > idle
```

例如，一个会话正在等待授权时，即使另一个会话开始工作，灯也会保持黄灯闪烁。遇到 `blocked` 时红灯优先级最高。会话结束提示不会打断活跃的 `permission`、`blocked`、`attention` 或 `done` 状态。

## ESP32-C3 后端

`pc_esp32_control` 不使用 MCP2221A GPIO，也不再使用 `SIGNAL_LIGHT_GREEN_PIN`、`SIGNAL_LIGHT_YELLOW_PIN`、`SIGNAL_LIGHT_RED_PIN` 或 `SIGNAL_LIGHT_ACTIVE_LOW`。当前支持三种 ESP32-C3 通信后端。

| 后端 | 配置 | 适合场景 |
| --- | --- | --- |
| `http` | `SIGNAL_LIGHT_HTTP_URL`，默认 `http://192.168.4.1` | ESP32-C3 AP/局域网，连续动画更稳定 |
| `serial` | `SIGNAL_LIGHT_SERIAL_PORT`、`SIGNAL_LIGHT_SERIAL_BAUD` | USB 直连、调试、烧录后验证 |
| `ble` | `SIGNAL_LIGHT_BLE_NAME` 或 `SIGNAL_LIGHT_BLE_ADDRESS` | 无线连接，不方便接入同一局域网时 |

本项目这套 RGB LED 实物默认颜色顺序是 `rbg`，用于匹配实际通道接线。如果你的硬件是标准 RGB 顺序，可改为 `rgb`。

```bash
export SIGNAL_LIGHT_BACKEND=http
export SIGNAL_LIGHT_HTTP_URL=http://192.168.4.1
export SIGNAL_LIGHT_ESP32_COLOR_ORDER=rbg
```

串口示例：

```bash
export SIGNAL_LIGHT_BACKEND=serial
export SIGNAL_LIGHT_SERIAL_PORT=/dev/ttyACM0
export SIGNAL_LIGHT_SERIAL_BAUD=115200
export SIGNAL_LIGHT_ESP32_COLOR_ORDER=rbg
```

BLE 示例：

```bash
export SIGNAL_LIGHT_BACKEND=ble
export SIGNAL_LIGHT_BLE_NAME=rgb-c3
```

## 无硬件试运行

安装项目后可以用 dry-run 验证灯语和 hook 映射，不会连接 ESP32-C3。

```bash
signal-light list
signal-light play working --dry-run --speed 0.05
signal-light codex-hook PermissionRequest --dry-run
signal-light claude-code-hook --event Notification --dry-run
```

macOS、Linux、Git Bash 或 WSL 也可以使用仓库内包装脚本：

```bash
./scripts/signal-light play working --dry-run
./scripts/codex-signal-hook PermissionRequest --dry-run
./scripts/claude-code-signal-hook --event Notification --dry-run
```

## 真实硬件验证

HTTP 后端：

```bash
signal-light test --backend http --http-url http://192.168.4.1
signal-light play working --backend http --http-url http://192.168.4.1
signal-light play idle --backend http --http-url http://192.168.4.1
```

串口后端：

```bash
pip install -e ".[serial]"
signal-light test --backend serial --serial-port COM5
signal-light play working --backend serial --serial-port COM5
signal-light play idle --backend serial --serial-port COM5
```

BLE 后端：

```bash
pip install -e ".[ble]"
signal-light test --backend ble --ble-name rgb-c3
```

如果亮起的颜色不对，调整 `SIGNAL_LIGHT_ESP32_COLOR_ORDER`。如果 ESP32-C3 没有响应，先分别验证 HTTP URL、串口号或 BLE 设备名/地址。

## Hook 配置示例

Windows 原生环境推荐在 JSON 中写 `.venv\Scripts` 下的绝对路径，详见 `pc_esp32_control/docs/WINDOWS_HOOKS.md`。

Codex 命令需要带事件名：

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\codex-signal-hook.exe PermissionRequest",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Claude Code 通过 stdin 传入事件 JSON，命令末尾不需要事件参数：

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\claude-code-signal-hook.exe",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```
