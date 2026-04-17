---
name: redmine-pmgr-opencode
description: 使用 Redmine 工单驱动 project-manager 与 OpenCode 的开发流程，自动抓取工单、创建 task/worktree、交给 OpenCode 执行，并在人工测试确认后完成 commit、merge、push。
version: 0.1.0
author: dwolf
license: MIT
required_environment_variables:
  - name: REDMINE_API_KEY
    prompt: Redmine API Key
    help: 用于读取工单详情与附件
    required_for: 读取 Redmine 工单
  - name: PMGR_API_TOKEN
    prompt: Project Manager API Token
    help: 如果 PMGR 未开启鉴权可留空
    required_for: 调用 project-manager API
metadata:
  hermes:
    tags: [Redmine, project-manager, OpenCode, Workflow, Topwhitech]
    config:
      - key: redmine.base_url
        description: Redmine 基础地址
        default: https://apredmine.topwhitech.com
        prompt: Redmine base URL
      - key: pmgr.base_url
        description: project-manager API 地址
        default: http://127.0.0.1:8710
        prompt: project-manager base URL
      - key: workflow.branch_prefix
        description: 创建 task 分支时使用的分支前缀
        default: fix
        prompt: Branch prefix
      - key: workflow.default_branch
        description: 目标项目默认基线分支
        default: main
        prompt: Default branch
---

# Redmine -> pmgr -> OpenCode

## When to Use

- 用户给出 Redmine 工单链接，希望基于工单内容自动推进开发流程
- 需要先解析工单描述和附件，再决定映射到哪个 `pmgr` 项目
- 需要在 task/worktree 中调用 OpenCode 执行修改
- 完成后必须停下来等待用户测试确认，再做 `commit -> merge -> push`

## References

- `references/workflow-contract.md`
- `references/project-manager-api.md`
- `config/project_map.json`

## Scripts

- `scripts/fetch_redmine_issue.py`：抓取工单详情并下载附件
- `scripts/summarize_issue_bundle.py`：把工单与附件整理成可交给 OpenCode 的执行摘要
- `scripts/pmgr_client.py`：调用 `project-manager` 的实际 API
- `scripts/summarize_opencode_progress.py`：把 OpenCode 增量消息整理成中文进度摘要
- `scripts/watch_opencode_progress.py`：持续轮询 OpenCode 增量消息并输出中文进度
- `scripts/watch_redmine_issue_progress.sh`：输入 `issue_url` 或 `session_id`，自动 bootstrap 并开始轮询
- `scripts/env.setup.sh`：快速导出所需环境变量

## Quick Start

先准备环境变量：

```bash
source /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/env.setup.sh
```

抓取工单并生成摘要：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/fetch_redmine_issue.py \
  --issue-url "https://apredmine.topwhitech.com/issues/34324" \
  --output-dir /tmp/redmine-34324

python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/summarize_issue_bundle.py \
  --bundle /tmp/redmine-34324/issue_bundle.json \
  --output /tmp/redmine-34324/issue_summary.md
```

用 `pmgr` 创建 task/worktree：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/pmgr_client.py create-workspace \
  --project appoker \
  --task issue-34324 \
  --branch-prefix fix \
  --source-branch main
```

拉取 OpenCode 过程增量并生成中文进度摘要：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/pmgr_client.py opencode-get-messages \
  --directory /Users/dwolf/devhub/projects/appoker/worktrees/issue-34324 \
  --session-id ses_xxx \
  --after-message-id msg_xxx \
  --limit 10 > /tmp/redmine-34324/opencode_messages.json

python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/summarize_opencode_progress.py \
  --messages-json /tmp/redmine-34324/opencode_messages.json
```

持续轮询并自动输出中文进度：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/watch_opencode_progress.py \
  --directory /Users/dwolf/devhub/projects/appoker/worktrees/issue-34324 \
  --session-id ses_xxx \
  --interval 30
```

如果只想从“现在开始”看后续新增进展，先做 bootstrap：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/watch_opencode_progress.py \
  --directory /Users/dwolf/devhub/projects/appoker/worktrees/issue-34324 \
  --session-id ses_xxx \
  --bootstrap latest \
  --once
```

之后再正常轮询：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/watch_opencode_progress.py \
  --directory /Users/dwolf/devhub/projects/appoker/worktrees/issue-34324 \
  --session-id ses_xxx \
  --interval 30
```

更顺手的封装：

```bash
bash /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/watch_redmine_issue_progress.sh \
  --issue-url "https://apredmine.topwhitech.com/issues/34324"
```

如果 `pmgr` 里的 task 记录已缺失，这个封装会按项目 `repo_path` 自动猜测：`worktrees/issue-<id>`，再继续查最近 session。
如果同一个 workspace 下有多个 session，这个封装会先打印最近几个候选，再默认选择最新一条继续观察。

或者直接给已有 session：

```bash
bash /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/watch_redmine_issue_progress.sh \
  --session-id ses_xxx \
  --directory /Users/dwolf/devhub/projects/appoker/worktrees/issue-34324
```

## Procedure

1. 从用户消息中提取 Redmine 工单 URL；若没有合法工单 URL，不要猜测。
2. 运行 `fetch_redmine_issue.py`，拿到：
   - 工单 id、标题、描述、项目名、状态、优先级
   - 附件元数据
   - 本地附件下载目录
3. 用 `config/project_map.json` 按 Redmine 项目名映射 `pmgr` 项目：
   - `AP -> appoker`
   - `APT -> appoker-tw-nf`
   - 若未命中映射，列出候选并停下来请求用户确认。
4. 运行 `summarize_issue_bundle.py`，生成面向 OpenCode 的执行摘要，至少包含：
   - 问题背景
   - 明确目标
   - 验收点
   - 附件摘要
   - 未能解析的附件
5. 先用 `pmgr_client.py health` 检查 `project-manager` 可用，再执行 `create-workspace`：
   - task 名固定为 `issue-<工单号>`
   - branch prefix 默认 `fix`
   - source branch 默认 `main`
6. 用 `pmgr_client.py opencode-health` 检查共享 OpenCode 服务健康状态。
7. 用 `pmgr_client.py opencode-create-session` 为目标 workspace 建立 OpenCode session。
8. 把执行摘要发给 OpenCode。提示中必须明确：
     - 只在当前 task worktree 内工作
     - 先检查代码和约束，再实现
     - 完成后返回结论、分析、修改内容、验证结果和剩余风险
     - 不要自动执行 merge 或 push
    调用消息接口时，payload 必须使用 `parts` 数组，而不是简单的 `message` 字符串。
9. 若用户要求过程同步，Hermes 应优先使用 `watch_opencode_progress.py`。若不想回放已有历史，先用 `--bootstrap latest --once` 初始化游标，再开始正常轮询。
10. OpenCode 完成后，Hermes 必须先用中文整理给用户审查，至少包含：
   - 结论：这次修复判断的问题根因或最佳诊断
   - 分析：为什么这样判断，依据了哪些代码或现象
   - 修改内容：改了哪些文件、哪些关键逻辑
   - 验证：已执行了什么本地验证
   - 风险：还有哪些不确定项或待确认点
11. 只有在用户已经看过上述中文汇总并明确确认效果后，才进入“等待提交/合并”阶段。
12. 在用户明确确认效果前，不要执行 `git commit`、`pmgr merge` 或 `git push`。
13. 用户确认后，再执行：
     - `git status`
     - `git add <relevant files>`
     - `git commit -m "fix: issue <id> <简短摘要>"`
     - `pmgr merge`
     - `git push origin main`

## OpenCode Prompt Contract

交给 OpenCode 的消息至少要包含：

```text
Issue: #34324
Project: appoker
Task branch prefix: fix
Task name: issue-34324

Summary:
<工单摘要>

Acceptance Criteria:
<验收点>

Attachment Notes:
<附件提炼>

Rules:
- Work only inside the provided task worktree.
- Do not merge or push.
- Report conclusion, analysis, changed files, verification steps, and residual risks.
- Stop after implementation and local verification so Hermes can wait for user testing.
```

## Pitfalls

- `project-manager` 文档里旧的 `pm_resolve_instance` / `pm_create_task_instance` 已经与代码不一致；这里必须调用实际存在的 `pm_resolve_workspace` / `pm_create_task_workspace`。
- 当前共享 OpenCode API 的消息 payload 需要 `parts` 数组，shell payload 需要显式的 `agent` 字段；不要照搬旧文档里的简化字段。
- 过程同步应基于 `opencode_get_messages` 做增量拉取，不要靠重复追问 OpenCode 来获取进度，否则会污染会话上下文。
- 若 `project-manager` 或共享 OpenCode 服务未启动，要先说明阻塞原因，不要继续编造结果。
- Redmine 附件可能是图片或二进制文件；无法解析时必须显式列出，不要假装已读取内容。
- 工单映射失败时，必须停下来让用户确认目标项目。
- 完成开发后，必须先把 OpenCode 的结论、分析、修改内容用中文整理给用户审查，再等待用户测试确认，不能直接提交到 `main`。

## Verification

最少执行以下核对：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/pmgr_client.py health
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/fetch_redmine_issue.py --issue-url "https://apredmine.topwhitech.com/issues/34324" --output-dir /tmp/redmine-34324 --metadata-only
```

成功标准：

- 能拿到工单 JSON
- 能正确把 `AP` 映射为 `appoker`，把 `APT` 映射为 `appoker-tw-nf`
- 能成功创建 task/worktree 或解析到现有 workspace
- OpenCode 执行完成后，Hermes 会停在等待测试确认阶段
