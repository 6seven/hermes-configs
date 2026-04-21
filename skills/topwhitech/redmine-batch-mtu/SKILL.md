---
name: redmine-batch-mtu
description: 解析 Redmine issues 列表链接中的工单集合，映射到对应 pmgr 项目，在 main 分支工作区下新建 OpenCode session，并以执行模式运行 `mtu <ids>`。
version: 0.1.0
author: dwolf
license: MIT
required_environment_variables:
  - name: PMGR_API_TOKEN
    prompt: Project Manager API Token
    help: 如果 PMGR 未开启鉴权可留空
    required_for: 调用 project-manager API
metadata:
  hermes:
    tags: [Redmine, Batch, MTU, project-manager, OpenCode, Topwhitech]
    config:
      - key: pmgr.base_url
        description: project-manager API 地址
        default: http://127.0.0.1:8710
        prompt: project-manager base URL
      - key: opencode.base_url
        description: OpenCode 共享服务地址，用于生成 Open Web 链接
        default: http://175.178.89.45:4100
        prompt: OpenCode shared server base URL
---

# Redmine Batch MTU

## When to Use

- 当用户消息以 `mtu ` 前缀显式触发时，进入这个 skill
- `mtu ` 后面可以是单个 Redmine 工单链接、工单列表链接、单个工单号，或逗号分隔的工单号集合
- 链接可以来自 `[Pasted ...]` 包裹文本
- 若参数里没有项目线索，默认走 `appoker`
- 需要在目标项目 `main` 分支工作区下新建一个 OpenCode session
- 需要让 OpenCode 处于执行模式，并真正执行 OpenCode 命令 `/mtu <ids>`

## Trigger Contract

- 只有当用户消息包含 `mtu ` 前缀时，才允许触发本 skill
- 若 `mtu ` 后面是单工单链接：提取该工单号并执行 `/mtu <id>`
- 若 `mtu ` 后面是工单列表链接：提取工单集合并执行 `/mtu <id1,id2,...>`
- 若 `mtu ` 后面是单个工单号或逗号分隔集合：直接把参数传给 `/mtu`
- 若参数格式不属于以上几类，进入本 skill 但回复 `参数格式不支持`

## References

- `../redmine-pmgr-opencode/config/project_map.json`

## Scripts

- `scripts/parse_redmine_issue_list.py`：从原始粘贴文本提取唯一 Redmine 列表链接、项目名和工单集合
- `scripts/run_batch_mtu.py`：解析输入、定位 main 工作区、新建 session，并在 OpenCode 中执行 `mtu`

## Supported Input

- `mtu https://apredmine.topwhitech.com/issues/34324`
- `mtu https://apredmine.topwhitech.com/projects/ap/issues?...&issue_id=34363%2C34389`
- `mtu [Pasted https://apredmine.topwhitech.com/projects/ap/issues?...&v%5Bissue_id%5D%5B%5D=34119%2C34243 ]`
- `mtu 34324`
- `mtu 34324,34325,34326`

## Procedure

1. 先检查用户消息是否包含 `mtu ` 前缀；没有则不要进入本 skill。
2. 解析 `mtu ` 后面的参数，按顺序尝试识别：
   - 单工单链接
   - 工单列表链接
   - 单个工单号
   - 逗号分隔工单号集合
3. 若参数格式不属于以上几类，回复 `参数格式不支持`。
4. 如果参数是工单列表链接，则按链接里的 Redmine 项目走 `project_map.json` 映射。
5. 如果参数是单工单链接、单工单号或工单号集合，默认走 `appoker`。
6. 执行前先向用户回显：
   - Redmine 项目
   - pmgr 项目
   - 工单集合
   - 待执行命令 `/mtu <ids>`
7. 用户确认后，调用 `pmgr_client.py resolve-workspace --project <project> --source-branch main`，解析 main 分支工作区目录。
8. 在该目录下调用 `pmgr_client.py opencode-create-session` 新建 session。
9. 发送执行模式消息给 OpenCode，并说明接下来会执行 `/mtu <ids>`。
10. 再调用 `pmgr_client.py opencode-run-shell`，在该 session 中执行 `/mtu <ids>`。
11. 返回给用户：
    - pmgr 项目
    - main 工作区目录
    - Open Web
    - session id
    - `pmgr session <session_id>`
    - 实际执行命令

## Pitfalls

- 这个 skill 不读取 Redmine 工单详情，也不需要 `REDMINE_API_KEY`。
- 若参数是工单列表链接且项目映射失败，必须明确指出未命中的 Redmine 项目，不要猜测。
- 执行目标固定是 `main` 分支工作区；不要为每个工单创建 `issue-*` worktree。
- `opencode-run-shell` 的 payload 需要显式提供 `agent` 与 `command`；复用 `pmgr_client.py`，不要另造 API 调用。
- 单工单链接、单工单号和工单号集合都固定走 `appoker`；只有列表链接才按 Redmine 项目映射。
- 生成 Open Web 需要 `opencode.base_url`；若地址不对，优先修正配置而不是改链接拼装规则。

## Quick Start

仅解析输入：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-batch-mtu/scripts/run_batch_mtu.py \
  --input-text 'mtu 34363,34389'
```

确认后执行：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-batch-mtu/scripts/run_batch_mtu.py \
  --input-text 'mtu https://apredmine.topwhitech.com/issues/34363' \
  --execute
```

## Verification

最少执行以下核对：

```bash
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-batch-mtu/scripts/parse_redmine_issue_list.py \
  --input-text 'mtu 34363,34389'
python3 /Users/dwolf/devhub/projects/hermes-configs/repo/skills/topwhitech/redmine-batch-mtu/scripts/run_batch_mtu.py \
  --input-text 'mtu https://apredmine.topwhitech.com/issues/34363'
```

成功标准：

- 能正确识别单工单链接、列表链接、单工单号、逗号分隔集合
- 能输出按顺序去重后的工单串
- 列表链接能正确把 `AP` / `APT` 映射到对应 pmgr 项目
- 无项目线索时默认走 `appoker`
