---
name: redmine-telegram-watcher
description: 轮询指派给我的 Redmine 工单，并在 AP/APT 项目内按 updated_on 发现增量后推送到 Telegram 私聊，不调用任何模型。
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
- 增量定义只看 `updated_on`
- 发现增量后推送到 Telegram 私聊
- 不希望调用任何模型，不消耗 token

## References

- `config/watch_projects.json`

## Scripts

- `scripts/poll_redmine_updates.py`：轮询 Redmine、比较状态并发送通知
- `scripts/send_telegram_message.py`：向 Telegram 发送文本消息
- `scripts/redmine_telegram_env.setup.sh`：快速生成 watcher 需要的环境变量
- `scripts/run_redmine_watcher_cron.sh`：cron 入口，按天写入日志

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
*/5 * * * * /usr/bin/env bash ~/.hermes/skills/topwhitech/redmine-telegram-watcher/scripts/run_redmine_watcher_cron.sh
```

日志会按天写到：

```text
~/.hermes/logs/redmine-watcher/YYYY-MM-DD.log
```

`run_redmine_watcher_cron.sh` 会自动清理 30 天前的旧日志。

## Procedure

1. 读取本地状态文件，默认是 `~/.hermes_redmine_watcher_state.json`。
2. 请求 Redmine 中“指派给我”的 issue 列表。
3. 仅保留项目名为 `AP`、`APT` 的工单。
4. 对每条工单提取 `id`、`subject`、`status`、`priority`、`updated_on`。
5. 用 `issue_id + updated_on` 判断是否是新增版本。
6. 首次运行若带 `--bootstrap`，只写基线，不发通知。
7. 非 bootstrap 模式下，对增量工单逐条发 Telegram 文本消息。
8. 推送成功后更新状态文件。

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
- 默认只看“指派给我”的工单，且只保留 `AP`、`APT`；如果未来扩展项目，优先改 `config/watch_projects.json`。
- 默认首次执行应使用 `--bootstrap`，避免把历史工单全部推到 Telegram。
- 推送目标优先取 `TELEGRAM_CHAT_ID`，没有再回退到 `TELEGRAM_HOME_CHANNEL`。
- Redmine 列表请求已做小分页、按 `updated_on:desc` 排序和重试退避；若仍偶发超时，优先重试，不要先改增量逻辑。
- cron 默认通过 `run_redmine_watcher_cron.sh` 写按天日志；不要再把长期日志直接追加到单个文件。
- 当前日志保留策略是 30 天；如果要调整，优先改 `run_redmine_watcher_cron.sh` 中的 `RETENTION_DAYS`。

## Verification

最少执行以下核对：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-telegram-watcher/scripts/poll_redmine_updates.py --dry-run
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-telegram-watcher/scripts/poll_redmine_updates.py --test-telegram
```

成功标准：

- 能从 Redmine 拉到工单列表
- 只保留 `AP`、`APT`
- dry-run 能输出增量工单摘要
- Telegram 测试消息能送达
