---
name: redmine-telegram-watcher
description: 轮询指派给我的 Redmine 工单，并在 AP/APT 项目内只推送高优先级或 Failed Test不通过 的 updated_on 增量到 Telegram 私聊，不调用任何模型。
version: 0.1.0
author: dwolf
license: MIT
required_environment_variables:
  - name: REDMINE_API_KEY
    prompt: Redmine API Key
    help: 用于读取 Redmine 工单列表
    required_for: 轮询 Redmine
  - name: TELEGRAM_BOT_TOKEN
    prompt: Telegram Bot Token
    help: 用于发送 Telegram 通知
    required_for: 推送 Telegram
metadata:
  hermes:
    tags: [Redmine, Telegram, Watcher, Cron, Topwhitech]
    config:
      - key: redmine.base_url
        description: Redmine 基础地址
        default: https://apredmine.topwhitech.com
        prompt: Redmine base URL
      - key: watcher.state_file
        description: 本地状态文件路径
        default: ~/.hermes_redmine_watcher_state.json
        prompt: State file path
      - key: watcher.log_file
        description: cron 日志文件路径
        default: ~/.hermes/logs/redmine-watcher.log
        prompt: Log file path
---

# Redmine Telegram Watcher

## When to Use

- 需要定时检查“指派给我”的 Redmine 工单更新
- 只保留项目 `AP`、`APT`
- 默认只推送高优先级或 `Failed Test不通过`
- 增量定义只看 `updated_on`
- 发现增量后推送到 Telegram 私聊
- 不希望调用任何模型，不消耗 token

## References

- `config/watch_projects.json`

## Scripts

- `scripts/poll_redmine_updates.py`：轮询 Redmine、比较状态并发送通知
- `scripts/send_telegram_message.py`：向 Telegram 发送文本消息
- `scripts/redmine_telegram_env.setup.sh`：快速生成 watcher 需要的环境变量

## Environment

优先读取以下环境变量：

- `REDMINE_BASE_URL`
- `REDMINE_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

若没有 `TELEGRAM_CHAT_ID`，会回退到：

- `TELEGRAM_HOME_CHANNEL`

## Quick Start

先准备环境变量：

```bash
source /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-telegram-watcher/scripts/redmine_telegram_env.setup.sh
```

首次建立基线，不推送历史工单：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-telegram-watcher/scripts/poll_redmine_updates.py --bootstrap
```

单次 dry-run，查看将要推送的内容但不发 Telegram：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-telegram-watcher/scripts/poll_redmine_updates.py --dry-run
```

测试 Telegram 连通性：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-telegram-watcher/scripts/poll_redmine_updates.py --test-telegram
```

## Cron

建议每 5 分钟执行一次：

```cron
*/5 * * * * /usr/bin/env bash -lc 'source ~/.hermes_skills.env 2>/dev/null || true; python3 ~/.hermes/skills/topwhitech/redmine-telegram-watcher/scripts/poll_redmine_updates.py >> ~/.hermes/logs/redmine-watcher.log 2>&1'
```

## Procedure

1. 读取本地状态文件，默认是 `~/.hermes_redmine_watcher_state.json`。
2. 请求 Redmine 中“指派给我”的 issue 列表。
3. 仅保留项目名为 `AP`、`APT` 的工单。
4. 再按 `config/watch_projects.json` 过滤：
   - `priority_whitelist`
   - `status_whitelist`
5. 对每条工单提取 `id`、`subject`、`status`、`priority`、`updated_on`。
6. 用 `issue_id + updated_on` 判断是否是新增版本。
7. 首次运行若带 `--bootstrap`，只写基线，不发通知。
8. 非 bootstrap 模式下，对增量工单逐条发 Telegram 文本消息。
9. 推送成功后更新状态文件。

## Message Format

```text
[Redmine 增量]
#34324 Triple Win Bounty：支持开启Bomb Pot、2-7 win
项目: AP
状态: Failed Test不通过
优先级: High
更新时间: 2026-04-18T10:30:00Z
链接: https://apredmine.topwhitech.com/issues/34324
```

## Pitfalls

- 这个 watcher 不调用任何模型；不要在轮询脚本里加 LLM 摘要逻辑。
- 默认只看“指派给我”的工单，且只保留 `AP`、`APT` 中高优先级或 `Failed Test不通过`；如果未来扩展规则，优先改 `config/watch_projects.json`。
- 默认首次执行应使用 `--bootstrap`，避免把历史工单全部推到 Telegram。
- 推送目标优先取 `TELEGRAM_CHAT_ID`，没有再回退到 `TELEGRAM_HOME_CHANNEL`。

## Verification

最少执行以下核对：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-telegram-watcher/scripts/poll_redmine_updates.py --dry-run
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-telegram-watcher/scripts/poll_redmine_updates.py --test-telegram
```

成功标准：

- 能从 Redmine 拉到工单列表
- 只保留符合项目与优先级/状态白名单的工单
- dry-run 能输出增量工单摘要
- Telegram 测试消息能送达
