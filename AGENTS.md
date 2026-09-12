# 个人留底仓库规则（用户确认：2026-09-12）

本仓库 `automaticgrasshopper/interactive-content-skills` 是用户个人研发留底仓库，不是团队正式资源发布仓库。

- 每次完成用户授权的修改后，自动提交并推送本次相关改动，不创建 PR，不额外询问是否提交。
- 不夹带无关改动，不强制推送，不覆盖他人工作。现有版本与测试副本按用户任务范围保留。
- 本仓库的 commit/push 仅用于留底，不等于正式上线或 Maxwell 同步。
- 正式目录在团队仓库 `world-sim-dev/nextplay-fe` 的 `agent-resources/`；本机为 `/Users/automaticgrasshopper/Documents/ChatGPT/影游发版/agent-resources/`。正式流程图路径为 `skills/episode-route-planner-biz/`。
- 正式目录的改动必须独立分支向团队仓库 main 提 PR，由管理员审核合并及同步；个人留底免 PR 规则不适用于正式资源。
- 操作前核对实际工作目录、git remote 和当前分支，不能把留底推送当作正式发版完成。
