# Windows 下配置 Codex CLI 和 Claude Code CLI Hook

本文说明如何在 Windows 原生环境中，把 Codex CLI 和 Claude Code CLI 的 hook 接到 `pc_esp32_control` 的 ESP32-C3 信号灯控制器。

`pc_esp32_control` 的灯语、hook 事件映射和硬件出口都以本项目实现为准：Windows 上推荐使用 pip 安装后的 console script，即 `signal-light.exe`、`codex-signal-hook.exe`、`claude-code-signal-hook.exe`。仓库 `scripts/` 下的 `codex-signal-hook`、`claude-code-signal-hook` 和 `install-hooks` 是 bash 包装脚本，更适合 macOS、Linux、Git Bash 或 WSL，不建议在原生 Windows 的 agent 配置中直接使用。

## 1. 安装 PC 端工具

在 PowerShell 中进入项目目录：

```powershell
cd D:\PartTime\2026\06\monitor\pc_esp32_control
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

按你实际使用的 ESP32-C3 通信方式安装可选依赖：

```powershell
# 串口
pip install -e ".[serial]"

# BLE
pip install -e ".[ble]"

```

HTTP 后端只使用 Python 标准库，不需要额外依赖。

确认入口命令已经生成：

```powershell
Get-Command signal-light
Get-Command codex-signal-hook
Get-Command claude-code-signal-hook
```

如果 Codex CLI 或 Claude Code CLI 不是从已激活 `.venv` 的 PowerShell 启动，hook 运行时可能找不到这些命令。更稳妥的方式是在 hook JSON 中写 `.venv\Scripts` 下的绝对路径。

## 2. 配置 ESP32-C3 后端

Hook 进程会继承启动 agent 时的环境变量。推荐把后端配置写成用户环境变量，然后重新打开 PowerShell、Codex CLI 或 Claude Code CLI。

本项目这套 ESP32-C3 RGB 灯实物默认使用 `rbg` 颜色顺序，让逻辑 green 发送到实际绿色通道。如果你的设备是标准 RGB 顺序，可以把 `SIGNAL_LIGHT_ESP32_COLOR_ORDER` 改成 `rgb`。

HTTP 示例：

```powershell
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_BACKEND", "http", "User")
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_HTTP_URL", "http://192.168.4.1", "User")
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_ESP32_COLOR_ORDER", "rbg", "User")
```

串口示例：

```powershell
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_BACKEND", "serial", "User")
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_SERIAL_PORT", "COM5", "User")
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_SERIAL_BAUD", "115200", "User")
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_ESP32_COLOR_ORDER", "rbg", "User")
```

BLE 示例：

```powershell
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_BACKEND", "ble", "User")
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_BLE_NAME", "rgb-c3", "User")
```

也可以只在当前 PowerShell 会话中临时设置：

```powershell
$env:SIGNAL_LIGHT_BACKEND = "http"
$env:SIGNAL_LIGHT_HTTP_URL = "http://192.168.4.1"
$env:SIGNAL_LIGHT_ESP32_COLOR_ORDER = "rbg"
```

先手工验证 HTTP 硬件链路：

```powershell
signal-light test --backend http --http-url http://192.168.4.1
signal-light play working --backend http --http-url http://192.168.4.1
signal-light play idle --backend http --http-url http://192.168.4.1
```

串口模式先确认 `COMx` 口号。设备管理器里通常显示为 `USB Serial Device (COM5)` 这类名称，也可以在 PowerShell 中查看：

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
```

然后验证串口硬件链路：

```powershell
pip install -e ".[serial]"
signal-light test --backend serial --serial-port COM5
signal-light play working --backend serial --serial-port COM5
signal-light play idle --backend serial --serial-port COM5
```

没有硬件时可以 dry-run：

```powershell
signal-light codex-hook PermissionRequest --dry-run
signal-light claude-code-hook --event Notification --dry-run
```

如果想让真实 hook 只打印动作、不碰硬件：

```powershell
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_DRY_RUN", "1", "User")
```

恢复真实硬件输出：

```powershell
[Environment]::SetEnvironmentVariable("SIGNAL_LIGHT_DRY_RUN", $null, "User")
```

## 3. Codex CLI hooks.json

Codex 的用户级 hook 配置文件是：

```text
%USERPROFILE%\.codex\hooks.json
```

在 PowerShell 中确认 hook 可执行文件的绝对路径：

```powershell
Resolve-Path .\.venv\Scripts\codex-signal-hook.exe
```

下面示例假设项目路径是 `D:\PartTime\2026\06\monitor\pc_esp32_control`。JSON 字符串里的反斜杠需要写成 `\\`：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\codex-signal-hook.exe SessionStart",
            "timeout": 5
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\codex-signal-hook.exe UserPromptSubmit",
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
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\codex-signal-hook.exe PreToolUse",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\codex-signal-hook.exe PostToolUse",
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
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\codex-signal-hook.exe PermissionRequest",
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
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\codex-signal-hook.exe Stop",
            "timeout": 5
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\codex-signal-hook.exe SessionEnd",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Codex hook 适配器会优先从命令参数读取事件名，所以每个 Codex 命令末尾都要带上事件名，例如 `PermissionRequest`。

如果你的项目路径里有空格，需要在 JSON 字符串中给可执行文件路径加转义双引号：

```json
"command": "\"C:\\Users\\Roy\\My Projects\\pc_esp32_control\\.venv\\Scripts\\codex-signal-hook.exe\" PermissionRequest"
```

当前实现的 Codex 事件映射：

| Codex 事件 | 信号名 | 行为 |
| --- | --- | --- |
| `SessionStart` | `session_start` | 绿灯常亮 |
| `UserPromptSubmit` | `thinking` | 绿、黄、红工作循环 |
| `PreToolUse` | `working` | 绿色呼吸 |
| `PostToolUse` | `tool_done` | 绿、黄、红工作循环 |
| `PermissionRequest` | `permission` | 黄灯闪烁 |
| `Stop` | `turn_end` | 清除非紧急会话状态 |
| `SessionEnd` | `session_end` | 短暂完成提示后恢复聚合状态 |

如果 hook stdin 的 JSON 载荷包含 `signal`、`signal_name`、`lamp_signal`，且值是本项目支持的信号名，会覆盖事件默认映射。载荷里出现 `status`、`state`、`error`、`failure`、`exception`、非零 `exit_status` 等失败标记时，会映射为 `blocked`。

## 4. Claude Code CLI settings.json

Claude Code 的用户级配置文件是：

```text
%USERPROFILE%\.claude\settings.json
```

在 PowerShell 中确认 hook 可执行文件的绝对路径：

```powershell
Resolve-Path .\.venv\Scripts\claude-code-signal-hook.exe
```

下面示例假设项目路径是 `D:\PartTime\2026\06\monitor\pc_esp32_control`。Claude Code 会通过 stdin 传入 hook JSON，当前适配器能从 stdin 里的 `event` 或 `hook_event_name` 读取事件名，所以命令末尾不需要事件参数：

```json
{
  "hooks": {
    "SessionStart": [
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
    ],
    "UserPromptSubmit": [
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
    ],
    "PreToolUse": [
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
    ],
    "PostToolUse": [
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
    ],
    "PostToolUseFailure": [
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
    ],
    "PreCompact": [
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
    ],
    "SubagentStart": [
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
    ],
    "SubagentStop": [
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
    ],
    "PermissionRequest": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "D:\\PartTime\\2026\\06\\monitor\\pc_esp32_control\\.venv\\Scripts\\claude-code-signal-hook.exe",
            "timeout": 10
          }
        ]
      }
    ],
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
    ],
    "Stop": [
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
    ],
    "SessionEnd": [
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

当前实现的 Claude Code 事件映射：

| Claude Code 事件 | 信号名 | 行为 |
| --- | --- | --- |
| `SessionStart` | `session_start` | 绿灯常亮 |
| `UserPromptSubmit` | `thinking` | 绿、黄、红工作循环 |
| `PreToolUse` | `working` | 绿色呼吸 |
| `PostToolUse` | `tool_done` | 绿、黄、红工作循环 |
| `PostToolUseFailure` | `blocked` | 红灯闪烁 |
| `PreCompact` | `working` | 绿色呼吸 |
| `SubagentStart` | `working` | 绿色呼吸 |
| `SubagentStop` | `tool_done` | 绿、黄、红工作循环 |
| `PermissionRequest` | `permission` | 黄灯闪烁 |
| `Notification` | `attention` | 黄灯闪烁 |
| `Stop` | `turn_end` | 清除非紧急会话状态 |
| `SessionEnd` | `session_end` | 短暂完成提示后恢复聚合状态 |

如果 Claude Code 的 `Stop` 载荷里 `stop_reason` 是 `max_tokens` 或 `error`，当前适配器会映射为 `blocked`。

## 5. 验证 hook 命令

不经过 agent，直接验证 Codex hook：

```powershell
.\.venv\Scripts\codex-signal-hook.exe UserPromptSubmit
.\.venv\Scripts\codex-signal-hook.exe PermissionRequest
.\.venv\Scripts\codex-signal-hook.exe Stop
```

验证 Claude Code hook：

```powershell
'{"event":"PreToolUse","session_id":"demo"}' | .\.venv\Scripts\claude-code-signal-hook.exe
'{"event":"Notification","session_id":"demo"}' | .\.venv\Scripts\claude-code-signal-hook.exe
'{"event":"PermissionRequest","session_id":"demo"}' | .\.venv\Scripts\claude-code-signal-hook.exe
```

验证状态聚合：

```powershell
signal-light status
signal-light play off
```

## 6. 关于自动安装器

本项目提供了 `signal-light install-hooks`，实现位置是 `signal_light/hook_installer.py`。它会检查并改写：

| Agent | 配置文件 |
| --- | --- |
| Codex | `%USERPROFILE%\.codex\hooks.json` |
| Claude Code | `%USERPROFILE%\.claude\settings.json` |

当前安装器写入的命令使用仓库内跨平台包装脚本：

```text
pc_esp32_control\scripts\codex-signal-hook
pc_esp32_control\scripts\claude-code-signal-hook
```

这两个文件是 bash 脚本。原生 Windows 推荐按本文手工写 `.venv\Scripts\*.exe` 绝对路径；只有在 Git Bash、MSYS2、WSL 或其他能执行这些脚本的环境中，才建议使用自动安装器直接写入 hook 配置：

```powershell
signal-light install-hooks --all -y
```

正式改配置前可以 dry-run：

```powershell
signal-light install-hooks --all --dry-run
```

安装器会保留同一事件上的其他 hook；如果改写已有配置，会创建带时间戳的备份文件。

## 7. 常见问题

Hook 没有反应：

- 重新打开运行 Codex CLI 或 Claude Code CLI 的终端，确保它继承了 `SIGNAL_LIGHT_*` 用户环境变量。
- 把 JSON 中的命令改成 `.venv\Scripts\codex-signal-hook.exe` 或 `.venv\Scripts\claude-code-signal-hook.exe` 的绝对路径。
- 先在 PowerShell 直接运行第 5 节的 hook 命令，确认不是硬件链路问题。

JSON 配置不生效：

- 确认路径分别是 `%USERPROFILE%\.codex\hooks.json` 和 `%USERPROFILE%\.claude\settings.json`。
- Windows 路径在 JSON 字符串中需要双反斜杠，例如 `D:\\PartTime\\...\\codex-signal-hook.exe`。
- 如果路径包含空格，给可执行文件路径加转义双引号，例如 `"\"C:\\My Projects\\...\\codex-signal-hook.exe\" PermissionRequest"`。
- 如果已有其他 hook，不要覆盖整份文件；只合并 `hooks` 下对应事件的数组项。

ESP32-C3 没有亮灯：

- HTTP 模式先确认 `signal-light test --backend http --http-url http://192.168.4.1` 成功。
- 串口模式确认 `SIGNAL_LIGHT_SERIAL_PORT` 是正确的 `COMx`。
- BLE 模式如果设备要求配对，先在 Windows 蓝牙设置中完成配对；连续动画更推荐 HTTP 或串口。
