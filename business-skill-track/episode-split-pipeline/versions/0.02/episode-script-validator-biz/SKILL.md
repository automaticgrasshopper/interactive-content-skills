---
name: episode-script-validator-biz
description: "当三阶段协调者已签发校验票据，且全新子任务提示带 STAGE_WORKER:validation、已验证 planning-handoff.json、writing-handoff.json 和缓存目录时，使用本 Skill。它逐集执行Enhancer增强、确定性结构验收、场面复检、独立冷读和受控局部修复，最后沿用原九字段合同生成正式三件套及投影授权。缺少合法阶段票据或任一交接时拒绝执行。"
---

# 剧本校验师

## 目标

读取已冻结的规划和Screenwriter原稿，逐集完成Enhancer增强复写、结构验收、场面与冷读检查、局部修复和单集放行；全部通过后按原`episode-generator-biz`合同组装正式九字段结果。

本 Skill是三阶段流水线中唯一拥有正式输出权的阶段。开始前完整读取：

- `references/split-pipeline-contract.md`
- `references/business-interface.md`
- `references/episode-output-schema.md`
- `references/external-output-boundary.md`

## 入口门禁

当前提示必须包含`STAGE_WORKER:validation`、缓存目录和校验票据路径。先运行：

```bash
python3 scripts/pipeline_guard.py claim validation --state <缓存目录>/pipeline-state.json --ticket <校验票据.json>
```

未取得`VALIDATION_WORKER_CLAIMED`不得读取Enhancer Reference、生成正式结果或投影。随后运行：

```bash
python3 scripts/stage_handoff.py planning-verify <缓存目录> --pipeline-state <缓存目录>/pipeline-state.json --planning-handoff <缓存目录>/planning-handoff.json
python3 scripts/stage_handoff.py writing-verify <缓存目录> --pipeline-state <缓存目录>/pipeline-state.json --planning-handoff <缓存目录>/planning-handoff.json --writing-handoff <缓存目录>/writing-handoff.json
```

两个命令均PASS才允许生成Enhancer输入。不得直接读取聊天中的剧本、跳过原稿回执，或把梗概当原稿校验。

## 每集处理顺序

同一时刻只处理当前一集。当前集完成全部步骤并取得单集验收回执后，才进入下一集。

### 1. 构造Enhancer输入

运行：

```bash
python3 scripts/build_enhancer_input.py <缓存目录>/screenplay-drafts/<分集编号>.md --boundary "<停止边界>" --enhancer-reference references/vimax-script-enhancer.md --dialogue-reference references/chinese-dialogue-craft.md --screenwriter-receipt <缓存目录>/screenwriter-receipts/<分集编号>.json --output <缓存目录>/enhancer-inputs/<分集编号>.txt
```

Enhancer只读取该文件。该输入必须逐字包含：

- 当前Screenwriter原稿
- 当前停止边界
- `vimax-script-enhancer.md`
- `chinese-dialogue-craft.md`
- 与当前原稿SHA-256一致的PASS回执

### 2. 增强复写

一次性生成`enhanced-screenplays/<分集编号>.md`。Enhancer可以完整改写场面表达、对白、话轮、停顿、反应和不改变因果的动作组织，不要求保留原稿原句；不得改变冻结事实、行动结果、选择、结局或停止边界。

增强稿原样装入`episodes/<分集编号>.md`正文区，二者必须逐字一致。正式九字段中的标题、梗概分析、关联资产、结局和互动节点来自冻结材料，不由Enhancer重写。

### 3. 确定性结构验收

增强完成后读取`references/character-appearance-validation.md`并登记首次出场证据，然后运行：

```bash
python3 scripts/validate_episode.py <缓存目录> <分集编号>
```

检查九字段、拓扑关系、资产白名单、正文与增强稿逐字一致、人物首次出场和停止边界。结构失败时只修对应结构问题；涉及正文表达的修改仍须回到Enhancer，不由验证器写稿。

### 4. 场面复检与独立冷读

完整读取：

- `references/dramatization-completion.md`
- `references/episode-quality-review.md`

退出增强工作区后，分别生成场面复检包和冷读包。两个检查者只报告问题、位置和原因，不补句、不改稿、不生成替代正文。

```bash
python3 scripts/dramatization_gate.py plan <缓存目录> <分集编号>
python3 scripts/dramatization_gate.py packet <缓存目录> <分集编号> --output <场面复检包.json>
python3 scripts/dramatization_gate.py seal <缓存目录> <分集编号> <场面复检结果.json>
python3 scripts/dramatization_gate.py verify-one <缓存目录> <分集编号>
python3 scripts/episode_quality_gate.py packet <缓存目录> <分集编号> --output <冷读包.json>
python3 scripts/episode_quality_gate.py seal <缓存目录> <分集编号> <冷读结果.json>
python3 scripts/episode_quality_gate.py verify-one <缓存目录> <分集编号>
```

检查重点包括：

- 梗概中的动作、阻力、反馈、调整和结果是否真正演出。
- 对话是否有人物意图、接话、反驳、迟疑和关系变化。
- 首次出场是否自然说明当下需要知道的身份、关系和重要性。
- 是否出现梗概式压缩、证据清单、作者总结、轮流汇报、重复说明或机械问答。
- 本集结尾是否停在冻结边界，没有抢演下一集。

### 5. 问题单与局部修复

两项复检均PASS时不制造空修复。任一失败时，两项都输出绑定当前正文指纹的发现文件，再运行：

```bash
python3 scripts/review_repair_gate.py merge <缓存目录> <分集编号> <场面发现.json> <冷读发现.json> --output <缓存目录>/merged-review-findings/<分集编号>.json
python3 scripts/review_repair_gate.py input <缓存目录> <分集编号> <缓存目录>/merged-review-findings/<分集编号>.json --reference references/vimax-local-repair.md --output <缓存目录>/review-repair-inputs/<分集编号>.txt
python3 scripts/review_repair_gate.py verify <缓存目录> <分集编号> <缓存目录>/repair-baselines/<分集编号>.md <缓存目录>/merged-review-findings/<分集编号>.json --receipt <缓存目录>/review-repair-receipts/<分集编号>.json
```

局部修复仍由隔离Enhancer执行，只改问题单命中的句子、行或相邻接缝；未授权行逐字不变。修复后更新增强稿和正式正文，旧结构、场面与冷读回执全部失效，再重新执行第3至5步。

问题覆盖整集、连续故事材料错误或必须改变冻结事实时，局部修复必须拒绝：

- 只是原稿整体不可用：回到`episode-screenwriter-biz`重写当前集，再重新生成写作交接。
- 故事、拓扑或梗概错误：回到`episode-branch-planner-biz`。

复检者不得直接重写整集，也不得为了通过检查把正文压成举证句、概念说明或人物轮流报码。

### 6. 单集放行

```bash
python3 scripts/episode_acceptance.py <缓存目录> <分集编号>
```

只有以下材料同时存在且指纹一致才允许进入下一集：

`适配源 → 连续故事材料 → 写作输入 → 原稿 → 原稿回执 → Enhancer输入 → 增强稿 → 正式正文 → 结构验收 → 场面回执 → 冷读回执 → 单集验收`

不得写完第一集后停住；未完成全部冻结分集时保持`正在生成剧本`并继续。

## 全体检查与正式组装

全部分集放行后运行：

```bash
python3 scripts/validate_user_intent_lock.py project <缓存目录>
python3 scripts/story_treatment_gate.py verify <缓存目录>
python3 scripts/validate_story_topology.py <缓存目录>/story-treatment.json <缓存目录>/topology.md --expected-endings E
python3 scripts/synopsis_set_gate.py verify <缓存目录>
python3 scripts/validate_mainline_projection.py <缓存目录>
python3 scripts/validate_character_appearances.py <缓存目录> --asset-catalog <缓存目录>/asset-catalog.json --introductions <缓存目录>/character-introductions.json
python3 scripts/dramatization_gate.py verify <缓存目录>
python3 scripts/episode_quality_gate.py verify <缓存目录>
python3 scripts/episode_acceptance.py <缓存目录> --all
```

全部PASS后，只能使用原业务组装器：

```bash
python3 scripts/assemble_business_output.py <缓存目录> <输出目录>/episode-business.json --completion-receipt <输出目录>/completion-receipt.json --handoff <输出目录>/episode-handoff.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_business_output.py <输出目录>/episode-business.json --asset-catalog <缓存目录>/asset-catalog.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/pipeline_guard.py authorize <缓存目录> <输出目录>/episode-business.json <输出目录>/completion-receipt.json <输出目录>/episode-handoff.json --state <缓存目录>/pipeline-state.json --ticket <校验票据.json> --output <输出目录>/projection-authorization.json --expected-endings E --expected-formal F --expected-failure X
```

授权命令内部重新执行`verify_deliverable.py`。只有同时输出`DELIVERABLE_ACCEPTED`和`PROJECTION_AUTHORIZATION_CREATED`才完成校验子任务。随后把正式三件套和授权路径返回协调者，不在当前子任务写项目路线。

组装器只能映射已经验证的增强稿，不得摘要、压缩或新增正文。`STRUCTURE_PASS`不是完成证明；一旦出现`NOT_A_COMPLETION_ATTESTATION`，必须保持正在最终验收，不得生成授权、正式slot或完成态。

最终只返回与原`episode-generator-biz`完全相同的九字段`分集列表`JSON，不返回内部文件、分析过程、问题单或凭证。

## 兼容性要求

- 保持原九字段名称、顺序、层级、类型、节点与边语义、资产关联和结局规则不变。
- 保持原`episode-generator-biz`能力标识和工程接收合同，不新增正式顶层字段。
- 创建、修改、重做和恢复都返回当前完整结果，不只返回变化节点。
- 未取得`DELIVERABLE_ACCEPTED`时不得结束、标记完成或正式投影。
- 不接受`work_episode_raw.json`、聊天手写结果或工程route作为正式组装源。
