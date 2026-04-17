# project-manager API

这个 skill 只依赖当前 `project-manager` 代码中实际存在的 Hermes API。

## Base URL

- 默认：`http://127.0.0.1:8710`
- 鉴权：若设置 `PMGR_API_TOKEN`，请求头带 `Authorization: Bearer <token>`

## 关键端点

### `POST /hermes/tools/pm_create_task_workspace`

用于创建 task 与 worktree。

请求示例：

```json
{
  "project_ref": "appoker",
  "task_ref": "issue-34324",
  "source_branch": "main",
  "branch_prefix": "fix"
}
```

### `POST /hermes/tools/opencode_health`

用于确认共享 OpenCode 服务是否可用。

### `POST /hermes/tools/opencode_create_session`

用于在目标 workspace 下创建 OpenCode session。

### `POST /hermes/tools/opencode_send_message`

用于把整理后的工单摘要交给 OpenCode。

当前共享服务要求 `payload.parts` 为数组，最少形如：

```json
{
  "parts": [
    {
      "type": "text",
      "text": "..."
    }
  ]
}
```

### `POST /hermes/tools/opencode_run_shell`

用于在当前 OpenCode session 内执行聚焦 shell 命令。

当前共享服务要求 shell payload 至少包含 `agent` 与 `command`：

```json
{
  "agent": "build",
  "command": "pwd"
}
```

### `POST /hermes/tools/opencode_get_messages`

用于读取某个 OpenCode session 的消息流，并支持按 `after_message_id` 做增量过滤。

请求示例：

```json
{
  "project_ref": "appoker",
  "task_ref": "issue-34324",
  "session_id": "ses_xxx",
  "after_message_id": "msg_xxx",
  "limit": 20
}
```

返回中的 `data.messages` 为过滤后的消息列表，`data.last_message_id` 可作为下一轮轮询游标。

## Open Web URL

`project-manager web` 的 `Open Web` 按钮会把以下三项拼成链接：

- `base_url`
- `directory`
- `session_id`

路径规则：

```text
/{base64url(directory)}/session/{session_id}?directory=<directory>
```

这个 skill 的 `scripts/emit_opencode_entrypoints.py` 会直接输出：

- `Open Web`
- `Session`

## 注意

- 旧文档里提到的 `pm_resolve_instance` / `pm_create_task_instance` 不再作为本 skill 的调用依据。
- 这个 skill 默认优先使用 `pm_create_task_workspace`，因为目标就是按工单创建 `issue-<id>` task。
