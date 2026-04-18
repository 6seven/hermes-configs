# 仓库说明

- 与用户使用中文交流。
- 这个仓库主要用于记录 `hermes-agent` 的相关配置；新增内容时优先保持配置文档化、可检索、命名直接。

# 当前仓库状态

- 当前根目录除 `.git/` 外没有已检出文件；开始工作前先确认用户是否希望新建结构，或是否有内容尚未同步到本地。
- 当前仓库还没有本地提交；不要假设已有脚本、测试、格式化或目录约定。
- `git status --short --branch` 显示当前分支为 `master`，且跟踪的 `origin/master` 缺失；执行依赖远端的 Git 操作前先核对远端状态。

# 工作约束

- 没有读到 `README`、清单文件、CI、`opencode.json` 或其他仓库内指令文件；仓库内缺少依据时，不要编造命令、流程或架构说明。
- 若要补充仓库结构，优先采用最小目录和最少文件，围绕 `hermes-agent` 配置本身组织，而不是预先搭建通用工程脚手架。

# 已落地配置

- `skills/topwhitech/redmine-telegram-watcher/` 已用于轮询“指派给我”的 Redmine 工单；当前默认推送 `AP`、`APT` 中所有 `updated_on` 发生变化的增量，避免漏消息。
- 当前用户 crontab 已安装 5 分钟轮询任务，并通过 `run_redmine_watcher_cron.sh` 写入按天日志；脚本会自动清理 30 天前旧日志。若要调整频率或命令，先检查 `crontab -l` 中的 `redmine-telegram-watcher` 行，避免重复写入。
