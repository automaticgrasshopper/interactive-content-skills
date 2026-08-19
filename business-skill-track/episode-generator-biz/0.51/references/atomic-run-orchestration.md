# 逐集原子写作与验收

全体梗概冻结后，当前任务严格串行推进：

```text
单集适配源 → 连续故事材料 → 短底稿 → 短底稿回执
→ Enhancer输入 → 唯一完整剧本 → 正式九字段单集
→ 确定性结构验收 → 单集Acceptance → 下一集
```

## 职责

- `ADAPT`生成当前适配源、连续故事材料和唯一写作输入。
- `WRITE_COMPACT_DRAFT`只读写作输入，依`compact-draft-writer.md`固定事实、出场、行动因果、状态变化和停止位置。
- `VALIDATE_COMPACT_DRAFT`检查短底稿格式、体量、实际话轮、动作反馈和状态变化，封存哈希并构建Enhancer输入。
- `ENHANCE`只读当前Enhancer输入，依`vimax-script-enhancer.md`与`chinese-dialogue-craft.md`一次写成完整剧本。
- 增强稿逐字成为正式正文；`VALIDATE_STRUCTURE`只验证九字段、正文同一性、资产、人物出场、选择和跳转，封存哈希。
- `ACCEPT_EPISODE`只绑定已经通过的动作，不重跑内容判断。

## 状态机

`ADAPT → WRITE_COMPACT_DRAFT → VALIDATE_COMPACT_DRAFT → ENHANCE → VALIDATE_STRUCTURE → ACCEPT_EPISODE`。

所有动作均由当前任务执行，不创建其他任务。每次安全提交后立即读取`run_state.py status`给出的唯一`next_actions`并继续；不得询问用户。活动租约表示当前任务正在执行该动作；上下文切分后续跑同一租约，租约过期则先执行`RECOVER_EXPIRED_LEASE`再自动重做。

其他分集只有在全部直接前置均为`EPISODE_ACCEPTED`后才能`ADAPT`。当前集Acceptance后才进入下一集；已验收正文退出活跃工作集。一次只推进一集的一个动作，不并发写集。

## 失败与恢复

任何失败只回到最早失效动作，不跨门禁继续：

- 适配材料失效：`REBUILD_ADAPTATION`。
- 短底稿遗漏冻结事实、人物出场、行动结果或状态变化：`REWRITE_COMPACT_DRAFT`，丢弃其后产物。
- 短底稿仍有效而Enhancer改变事实或越过边界：`RERUN_ENHANCE`。
- 纯回执失效：`RESEAL_STRUCTURE`或`REBIND_ACCEPTANCE`。

返修必须完整重做当前动作，不对已提交正文做局部补丁。内容门禁失败属于内部运行态；当前任务自行定位、返修、复验并继续，只有真正缺少用户输入、用户要求彼此冲突或需要扩大授权时才对外询问。

## 产物

- `ADAPT`：`episode-adaptation-sources`、`episode-story-materials`、`episode-writing-inputs`。
- `WRITE_COMPACT_DRAFT`：`compact-drafts`。
- `VALIDATE_COMPACT_DRAFT`：`compact-draft-receipts`、`enhancer-inputs`。
- `ENHANCE`：`enhanced-screenplays`。
- `VALIDATE_STRUCTURE`：`episodes`、`episode-structure-receipts`。
- `ACCEPT_EPISODE`：`episode-acceptance-receipts`。

全部分集Acceptance后，当前任务继续组装和验证正式业务结果；任何缺失、哈希漂移或状态未闭合都不得交付。
