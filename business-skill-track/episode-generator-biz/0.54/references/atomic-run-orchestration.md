# 逐集原子编排

本文件是逐集阶段的唯一执行合同。先读`generative-execution-integrity.md`，随后只加载当前动作指定的输入和Reference。任何时刻只执行`workflow_state.py CACHE_ROOT`返回的一个动作；安全提交后立即重新读取状态，不自行规划动作列表。

## 状态链

```text
ADAPT → WRITE_EPISODE → VALIDATE_STRUCTURE → REVIEW_EPISODE → ACCEPT_EPISODE
```

- `ADAPT`：从冻结梗概和故事事实确定性建立适配源、连续故事材料和唯一写作输入。
- `WRITE_EPISODE`：只读当前标准输入及`vimax-screenwriter.md`、`chinese-dialogue-craft.md`和必要题材Reference，一次写成`screenplays/<episode-id>.md`。
- `VALIDATE_STRUCTURE`：先运行`build_episode_artifact.py`把完整剧本确定性封装为九字段私有单集，再运行`episode_structure_gate.py seal`检查资产、格式、故事与停止边界绑定、抽象占位和跨集模板重复，并建立冷读材料包。
- `REVIEW_EPISODE`：只读当前冷读材料包及`episode-quality-review-lite.md`，完成五项独立冷读。它只能判定，不能补写正文。
- `ACCEPT_EPISODE`：验证当前全部哈希与回执，封存单集验收。

两个生成动作分别是完整写作和轻量冷读。不得增加短底稿、Enhancer、第三版正文、第二轮审稿或自建生成脚本。

## 原子执行

每个动作先用`run_state.py claim`领取当前集租约；生成动作只接受状态机给出的`standard_input`。成功产物必须与`action_contracts.py`的输出集合完全一致，再用`run_state.py complete`提交。一次只领取一个动作、一个分集，提交后清空当前集正文关注点，再运行`workflow_state.py`。

适配和校验命令必须使用 Skill 随包脚本。禁止在缓存中创建程序或用循环、模板替换、复制拼接批量生成多集；`validate_execution_integrity.py`发现此类源码时不得继续。

## 失败与返修

- 完整写作未形成可演行动链，或确定性结构检查发现摘要骨架、登记式人物介绍、越界、资产错误、跨集模板复用：`REWRITE_EPISODE`，保留适配材料，整集重写。
- 冷读返回FAIL：先用`episode_quality_gate.py prepare-rewrite`封存最多三个带正文锚点的问题，再以`content`失败提交`REVIEW_EPISODE`。状态回到`ADAPTED`；下一次`WRITE_EPISODE`只读自动生成的返修输入，整集重写。
- 冷读候选格式或哈希错误属于编排失败，修复候选或重新冷读，不修改正文。
- 结构回执损坏但正文有效：`RESEAL_STRUCTURE`；冷读回执损坏：`REREVIEW_EPISODE`；验收绑定损坏：`REBIND_ACCEPTANCE`。
- 同一内容动作连续五次不通过或同一编排动作连续三次恢复失败才停止。其余情况自动从状态文件续跑，不询问用户。

任何返修都只保留最早仍有效的上游产物，禁止手写PASS、复制旧回执或让审核动作直接改稿。

## 上下文切分恢复

已提交动作以`run-state.json`及哈希为准。活动租约仍有效则只恢复该动作；租约过期先运行`recover-expired-lease`再重做。不得重新读回全部已完成剧本，不得从第一集重跑，也不得建立批量脚本“补进度”。

全部分集进入`EPISODE_ACCEPTED`后，状态机才返回`ASSEMBLE_DELIVERABLE`。
