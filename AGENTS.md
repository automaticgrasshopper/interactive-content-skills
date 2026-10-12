# 个人留底仓库规则（用户确认：2026-09-12）

本仓库 `automaticgrasshopper/interactive-content-skills` 是用户个人研发留底仓库，不是团队正式资源发布仓库。

- 每次完成用户授权的修改后，自动提交并推送本次相关改动，不创建 PR，不额外询问是否提交。
- 不夹带无关改动，不强制推送，不覆盖他人工作。现有版本与测试副本按用户任务范围保留。
- 本仓库的 commit/push 仅用于留底，不等于正式上线或 Maxwell 同步。
- 正式目录在团队仓库 `world-sim-dev/nextplay-fe` 的 `agent-resources/`；本机为 `/Users/automaticgrasshopper/Documents/ChatGPT/影游发版/agent-resources/`。正式流程图路径为 `skills/episode-route-planner-biz/`。
- 正式目录的改动必须独立分支向团队仓库 main 提 PR，由管理员审核合并及同步；个人留底免 PR 规则不适用于正式资源。
- 操作前核对实际工作目录、git remote 和当前分支，不能把留底推送当作正式发版完成。

## 蚂蚱实验资源长期授权（用户明确：2026-10-12）

- 可以直接修改用户自己的 Maxwell 预设“蚂蚱测试探索”（`8bf0ce65-3d52-4819-97d7-9afbb5751203`）的 SP，以及三个实验 Skill：`mazha-outline-route-1008`、`mazha-screenplay-1008`、`mazha-asset-image-direct-1008`。
- 使用已登录的 Maxwell Studio 后台即可，不需要 CLI key。不要因 CLI 未配置而要求用户重复配置或重复授权。
- 本地来源为 `business-skill-track/mazha-exploration-20260924/split-creation/`。前端在用户实验分支 `codex/mazha-story-lab-20260924` 修改、测试；不改共享后端，不合并或正式发布。
- 本授权跨会话持续有效；不得扩大到其他预设、正式 Skill 或共享平台。
