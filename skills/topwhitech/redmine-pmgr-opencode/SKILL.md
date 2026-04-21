---
name: redmine-pmgr-opencode
description: 使用 Redmine 工单驱动 project-manager 与 OpenCode 的计划模式交接流程，自动抓取工单、创建 task/worktree、创建 OpenCode session，并返回 Open Web 与本地 session 入口。
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

- 用户给出单个 Redmine 工单链接，希望基于工单内容自动推进开发流程
- 只处理形如 `https://apredmine.topwhitech.com/issues/<id>` 的单工单链接
- 如果输入是 Redmine 列表链接 `/projects/<project>/issues?...`，应改走 `redmine-batch-mtu`
- 需要先解析工单描述和附件，再决定映射到哪个 `pmgr` 项目
- 需要先把工单整理后交给 OpenCode 的 `plan mode`
- 需要直接返回 Open Web 链接和本地 `pmgr session <session_id>` 入口

## References

- `references/workflow-contract.md`
- `references/project-manager-api.md`
- `config/project_map.json`

## Scripts

- `scripts/fetch_redmine_issue.py`：抓取工单详情并下载附件
- `scripts/summarize_issue_bundle.py`：把工单与附件整理成可交给 OpenCode 的执行摘要
- `scripts/pmgr_client.py`：调用 `project-manager` 的实际 API
- `scripts/emit_opencode_entrypoints.py`：输出 `Open Web` 与 `Session` 两段入口信息
- `scripts/summarize_opencode_progress.py`：调试时把 OpenCode 增量消息整理成中文进度摘要
- `scripts/watch_opencode_progress.py`：调试时持续轮询 OpenCode 增量消息
- `scripts/watch_redmine_issue_progress.sh`：调试时输入 `issue_url` 或 `session_id` 观察 session
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

输出 OpenCode 入口：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-pmgr-opencode/scripts/emit_opencode_entrypoints.py \
  --base-url http://175.178.89.45:4100 \
  --directory /Users/dwolf/devhub/projects/appoker/worktrees/issue-34324 \
  --session-id ses_xxx
```

调试时如需观察 OpenCode 增量消息：

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

调试用封装：

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

1. 从用户消息中提取单个 Redmine 工单 URL；若没有合法单工单 URL，不要猜测。
   - 只接受 `https://apredmine.topwhitech.com/issues/<id>` 这类链接。
   - 如果输入是 `/projects/<project>/issues?...`、包含 `issue_id=` 或 `v[issue_id][]=` 的列表链接，不要进入本 skill，应改走 `redmine-batch-mtu`。
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
   - 当前处于 `plan mode`，先检查代码和约束，不要修改代码
   - 返回结论、分析、涉及文件、实施计划、验证计划和风险
   - 不要自动执行 merge 或 push
   调用消息接口时，payload 必须使用 `parts` 数组，而不是简单的 `message` 字符串。
9. session 建好并发出 `plan mode` 消息后，Hermes 直接返回两段内容，分开展示：
   - `Open Web`：对应 project-manager web 按钮打开的链接
   - `Session`：`pmgr session <session_id>`
10. 默认不再同步轮询 OpenCode 过程消息；`watch_*` 脚本只作为调试工具保留。
11. 后续开发默认由用户在 Open Web 或本地 `pmgr session <session_id>` 中继续推进。
12. 若用户之后要求继续由 Hermes 收尾，再回到审查、测试确认、提交流程。
13. 在用户明确确认效果前，不要执行 `git commit`、`pmgr merge` 或 `git push`。
14. 用户确认后，再执行：
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
- You are in plan mode: inspect first and do not modify files yet.
- Do not merge or push.
- Report conclusion, analysis, files to inspect/change, implementation plan, verification plan, and residual risks.
```

## Pitfalls

- `project-manager` 文档里旧的 `pm_resolve_instance` / `pm_create_task_instance` 已经与代码不一致；这里必须调用实际存在的 `pm_resolve_workspace` / `pm_create_task_workspace`。
- 当前共享 OpenCode API 的消息 payload 需要 `parts` 数组，shell payload 需要显式的 `agent` 字段；不要照搬旧文档里的简化字段。
- 当前主流程默认不做过程同步；`watch_*` 脚本只作为调试工具保留。
- 若 `project-manager` 或共享 OpenCode 服务未启动，要先说明阻塞原因，不要继续编造结果。
- Redmine 附件可能是图片或二进制文件；无法解析时必须显式列出，不要假装已读取内容。
- 如果用户贴的是 Redmine 工单列表链接，而不是单工单链接，应切到 `redmine-batch-mtu`，不要在这里猜第一个工单或拆列表处理。
- 工单映射失败时，必须停下来让用户确认目标项目。
- 当前主流程默认只做到 session 入口交接；如果用户要求继续由 Hermes 执行开发，再进入后续审查与提交流程。

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
- OpenCode session 能成功创建，并能输出 `Open Web` 与 `Session` 两段入口信息
