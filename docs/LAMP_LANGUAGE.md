# AI Agent 交通信号灯状态语言

本项目使用一个红、黄、绿三色交通信号灯模型，作为 Codex、Claude Code 或其他 AI agent 的环境状态显示器。

灯语刻意保持简单：当前灯效必须直接表示当前状态。这里没有需要记忆的启动动画，也没有“先闪一下、稍后再解释含义”的模式。只要 Codex 正在工作或需要你处理，灯效就会持续运行，直到新的 hook 事件改变状态。唯一的短暂提示是会话完成提示：某个会话结束时可以短暂闪一下绿灯，然后恢复到当前聚合状态。

注意：早期说明曾把 `permission` 描述为红灯权限告警；当前代码和测试里 `permission` 实际使用黄灯闪烁，`blocked` 才是红灯闪烁。本文档按当前代码行为描述。

## 状态语义

| 灯效 | 含义 | 人需要做什么 |
| --- | --- | --- |
| 绿灯常亮 | Codex 空闲 | 不需要处理 |
| 绿灯呼吸 | Codex 正在使用工具、编辑文件、运行命令或测试 | 等待 |
| 绿、黄、红慢速循环 | Codex 正在思考或处于工具调用间状态 | 等待 |
| 黄灯闪烁 | Codex 明确需要你阅读、确认或继续 | 有空时查看 Codex |
| 红灯闪烁 | Codex 阻塞、失败或无法继续 | 立即查看 Codex |
| 全灭 | 手动清除 | 不需要处理 |

这就是完整灯语。

## 信号名称

CLI 暴露了稳定的信号名称，方便 hook 和其他 agent 调用：

| 信号名 | 灯效 | 含义 |
| --- | --- | --- |
| `idle` | 绿灯常亮 | Agent 空闲 |
| `thinking` | 绿、黄、红慢速循环 | Agent 已收到提示词，正在思考 |
| `working` | 绿灯呼吸 | Agent 正在使用工具、编辑文件、运行命令或测试 |
| `tool_done` | 绿、黄、红慢速循环 | 一次工具调用已完成，但 agent 仍在工作流中 |
| `attention` | 黄灯闪烁 | Agent 明确希望你阅读或继续 |
| `done` | 黄灯闪烁 | 任务完成，建议阅读最终答复 |
| `permission` | 黄灯闪烁 | Codex 请求授权或需要明确批准 |
| `blocked` | 红灯闪烁 | Agent 无法继续，需要人工介入 |
| `session_start` | 绿灯常亮 | Codex 会话开始并处于空闲态 |
| `session_end` | 短暂绿灯完成提示，然后恢复聚合状态 | Codex 会话结束 |
| `session_done` | 短暂绿灯闪烁 | 内部使用的单会话完成提示 |
| `off` | 全灭 | 清除所有灯 |

## Codex Hook 映射

| Codex 事件 | 信号名 | 灯效 |
| --- | --- | --- |
| `SessionStart` | `session_start` | 绿灯常亮 |
| `UserPromptSubmit` | `thinking` | 绿、黄、红慢速循环 |
| `PreToolUse` | `working` | 绿灯呼吸 |
| `PostToolUse` | `tool_done` | 绿、黄、红慢速循环 |
| `PermissionRequest` | `permission` | 黄灯闪烁 |
| `Stop` | `turn_end` | 清除非紧急会话状态 |
| `SessionEnd` | `session_end` | 短暂绿灯完成提示，然后恢复聚合状态 |

`turn_end` 是 hook 专用的控制状态，不是公开灯效。它会移除该会话的非紧急工作状态，但保留已有的 `permission` 或 `blocked` 告警。

如果 hook 载荷通过结构化字段报告失败，例如 `status`、`state`、`error`、`failure`、`exception` 或非零 `exit_status`，适配器会使用 `blocked`，也就是红灯闪烁。

动画状态是持久的。命令会启动一个小型后台工作进程并立即返回，让 Codex hook 保持快速。下一个稳定状态会先停止后台工作进程，再设置自己的灯效。`Stop` 被视为正常回合结束，因此它会清除工作状态，而不是在每次回答后闪黄灯。

工作循环里包含亮度级别，ESP32-C3 后端会把它转换成 RGB 亮度命令。

Codex hook 状态是会话感知的。每个会话都会保存自己的最新信号，然后物理灯显示优先级最高的聚合状态：

```text
红灯闪烁 > 黄灯闪烁 > 绿色呼吸/工作循环 > 绿灯常亮
```

例如，一个 Codex 会话正在等待授权时，即使另一个会话开始工作，灯也会保持黄灯闪烁。一个会话等待你阅读结果时，如果另一个会话开始工作，灯也会保持黄灯闪烁。遇到 `blocked` 时红灯优先级最高。

当一个已跟踪会话结束时，运行时会短暂闪绿灯，让完成事件可见。提示结束后会重新计算聚合状态：如果其他会话仍在工作，就恢复绿色呼吸；如果没有剩余会话，就回到绿灯常亮。红灯和黄灯告警具有更高优先级，因此绿色完成提示不会打断活跃的 `permission`、`blocked`、`attention` 或 `done` 状态。

## ESP32-C3 后端

CLI 默认使用 HTTP 后端，默认地址是 `http://192.168.4.1`。也可以通过 `SIGNAL_LIGHT_BACKEND=http|serial|ble` 切换通信方式。

## 无硬件试运行

```bash
./scripts/signal-light list
./scripts/signal-light play working --dry-run
./scripts/signal-light play attention --dry-run
./scripts/signal-light codex-hook PermissionRequest --dry-run
```

## 使用真实硬件试运行

```bash
./scripts/signal-light test
./scripts/signal-light play working
./scripts/signal-light play attention
./scripts/signal-light play permission
./scripts/signal-light play idle
./scripts/signal-light play off
./scripts/signal-light status
```

如果亮起的灯颜色不对，调整 `SIGNAL_LIGHT_ESP32_COLOR_ORDER`。本项目默认是 `rbg`，标准 RGB 设备可设为 `rgb`。

包装脚本会避免在仓库中写入 `__pycache__` 文件。默认情况下，它们会优先使用 `.venv/bin/python`，不存在时回退到 `python3`。如果希望包装脚本通过 `uv run` 执行，设置：

```bash
export SIGNAL_LIGHT_USE_UV=1
```

## Claude Code Hook 映射

| Claude Code 事件 | 信号名 | 灯效 |
| --- | --- | --- |
| `SessionStart` | `session_start` | 绿灯常亮 |
| `UserPromptSubmit` | `thinking` | 绿、黄、红慢速循环 |
| `PreToolUse` | `working` | 绿灯呼吸 |
| `PostToolUse` | `tool_done` | 绿、黄、红慢速循环 |
| `PostToolUseFailure` | `blocked` | 红灯闪烁 |
| `PreCompact` | `working` | 绿灯呼吸 |
| `SubagentStart` | `working` | 绿灯呼吸 |
| `SubagentStop` | `tool_done` | 绿、黄、红慢速循环 |
| `PermissionRequest` | `permission` | 黄灯闪烁 |
| `Notification` | `attention` | 黄灯闪烁 |
| `Stop` | `turn_end` | 清除非紧急会话状态 |
| `SessionEnd` | `session_end` | 短暂绿灯完成提示，然后恢复聚合状态 |

如果 `Stop` 携带的 `stop_reason` 是 `max_tokens` 或 `error`，适配器会使用 `blocked`，而不是清除状态。

## Claude Code settings.json 示例

把 hook 添加到 `~/.claude/settings.json`，也可以添加到项目级 `.claude/settings.json`：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/claude-code-signal-hook",
            "timeout": 5
          }
        ],
        "matcher": ""
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/claude-code-signal-hook",
            "timeout": 5
          }
        ],
        "matcher": ""
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/claude-code-signal-hook",
            "timeout": 5
          }
        ],
        "matcher": ""
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/claude-code-signal-hook",
            "timeout": 5
          }
        ],
        "matcher": ""
      }
    ],
    "PostToolUseFailure": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/claude-code-signal-hook",
            "timeout": 5
          }
        ],
        "matcher": ""
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/claude-code-signal-hook",
            "timeout": 10
          }
        ],
        "matcher": ""
      }
    ],
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/claude-code-signal-hook",
            "timeout": 5
          }
        ],
        "matcher": ""
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/claude-code-signal-hook",
            "timeout": 5
          }
        ],
        "matcher": ""
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/claude-code-signal-hook",
            "timeout": 5
          }
        ],
        "matcher": ""
      }
    ]
  }
}
```

说明：Codex hook 需要通过命令参数传入事件名；Claude Code 会通过 stdin 传入 JSON 事件数据，所以 hook 命令不需要事件参数。

## Codex hooks.json 示例

把命令 hook 添加到 `~/.codex/hooks.json`。如果你已经有其他 hook，应保留它们：

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/codex-signal-hook UserPromptSubmit",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/codex-signal-hook PreToolUse",
            "timeout": 5
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/codex-signal-hook PermissionRequest",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/Users/liusixian/Develop/starlight36/signal-light/scripts/codex-signal-hook Stop",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```
