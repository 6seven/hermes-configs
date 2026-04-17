# Workflow Contract

## 输入

- 一个 Redmine 工单 URL，例如：`https://apredmine.topwhitech.com/issues/34324`

## 固定规则

1. 必须先抓工单，再做项目映射。
2. 必须尝试读取附件；无法解析的附件要显式列出。
3. task 名固定为 `issue-<工单号>`。
4. 默认 branch prefix 是 `fix`。
5. 若项目映射失败，必须停下来请求确认。
6. 若用户要求过程同步，Hermes 必须定期拉取 OpenCode session 增量消息，并整理成中文进度摘要同步给用户。
7. 完成开发后，Hermes 必须先把 OpenCode 的结果整理成中文审查摘要给用户。
8. 只有在用户明确确认效果后，才允许执行 `commit -> merge -> push`。

## 输出阶段

### 阶段 A：开发完成

应向用户汇报：

- 目标项目
- task/worktree 信息
- OpenCode 结论
- OpenCode 分析
- OpenCode 修改内容
- 已执行的本地验证
- 剩余风险
- 明确提醒现在等待用户审查与测试确认

### 阶段 A-1：过程同步

若启用过程同步，应向用户汇报：

- 当前结论或新发现
- 当前分析或排查方向
- 正在修改或刚修改的文件
- 已完成的本地验证
- 当前阻塞或风险
- 仅同步新增内容，不要重复刷屏

### 阶段 B：测试确认后

应执行：

1. `git add`
2. `git commit`
3. `pmgr merge`
4. `git push origin main`

并向用户汇报提交 hash 与 push 结果。
