# Workflow Contract

## 输入

- 一个 Redmine 工单 URL，例如：`https://apredmine.topwhitech.com/issues/34324`

## 固定规则

1. 必须先抓工单，再做项目映射。
2. 必须尝试读取附件；无法解析的附件要显式列出。
3. task 名固定为 `issue-<工单号>`。
4. 默认 branch prefix 是 `fix`。
5. 若项目映射失败，必须停下来请求确认。
6. 默认只创建 OpenCode session 并发出 `plan mode` 首条消息，不做过程同步。
7. Hermes 必须返回两个入口，分开展示：`Open Web` 与 `Session`。
8. 只有用户之后明确要求继续由 Hermes 执行开发时，才进入审查、测试确认与提交阶段。

## 输出阶段

### 阶段 A：Plan Handoff

应向用户汇报：

- 目标项目
- task/worktree 信息
- Open Web
- Session
- 明确说明当前 session 已经以 `plan mode` 打开

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
