---
name: episode-screenwriter-biz
description: "当三阶段协调者已签发写作票据，且全新子任务提示带 STAGE_WORKER:writing、已验证 planning-handoff.json 和缓存目录时，使用本 Skill。它逐集完成连续故事适配、Screenwriter原稿和原稿回执，不修改拓扑与梗概，不做Enhancer增强，不返回正式业务结果；全部原稿通过后生成 writing-handoff.json 并返回协调者。"
---

# 剧本创作师

## 目标

把冻结拓扑与全体梗概逐集写成可表演的Screenwriter原稿。每集必须完成适配材料、连续写作输入、原稿和原稿回执，全部通过后生成不可变的`writing-handoff.json`并返回协调者。

本 Skill不生成增强稿，不做场面复检或冷读，不组装正式九字段业务JSON。开始前完整读取`references/split-pipeline-contract.md`。

## 入口门禁

当前提示必须包含`STAGE_WORKER:writing`、缓存目录和写作票据路径。先运行：

```bash
python3 scripts/pipeline_guard.py claim writing --state <缓存目录>/pipeline-state.json --ticket <写作票据.json>
```

未取得`WRITING_WORKER_CLAIMED`不得读取写作Reference、生成原稿或自行切换阶段。随后运行：

```bash
python3 scripts/stage_handoff.py planning-verify <缓存目录> --pipeline-state <缓存目录>/pipeline-state.json --planning-handoff <缓存目录>/planning-handoff.json
```

未取得`PLANNING_HANDOFF_PASS`不得写任何原稿，也不得凭聊天上下文重建缺失规划。

只改正文表达或对白时，仍须存在与当前正式结果一致的规划交接；修改范围按原分集合同限制，未授权分集逐字不变。

## 读取边界

- 适配阶段读取`references/episode-story-adapter.md`和脚本生成的当前集适配源。
- Screenwriter只读取`references/vimax-screenwriter.md`、`references/chinese-dialogue-craft.md`和当前`episode-writing-inputs/<episode-id>.txt`。
- 当前题材实际命中时才读取`references/genre-direction.md`。
- 出现推动剧情的书面信息时才读取`references/written-text-to-dialogue.md`。
- 原稿完成后才读取`references/character-appearance-validation.md`，登记首次出场证据。
- 不读取Enhancer、场面复检、冷读、局部修复、业务组装或验收答案。

情绪脊、完整故事、审核问题、旧稿、未来集正文和验证脚本不得进入Screenwriter工作区。

## 工作批次

按冻结拓扑把相邻因果节点划成不超过三集的批次。共同主线、互斥分支、汇合段和结局段分别成批；批次不改变拓扑。

- 同一时刻只写当前一集。
- 当前集全部直接前置分集必须已经完成原稿，或在续写模式下具有已放行真实结尾。
- 不得先批量生成全体短文本，再补原稿和回执。
- 每集原稿回执PASS后才开始下一集。

## 每集流程

### 1. 建立适配源

```bash
python3 scripts/build_episode_adaptation_source.py <缓存目录> <分集编号> --output <缓存目录>/episode-adaptation-sources/<分集编号>.json
```

适配源只包含当前梗概、当前节点、已完成直接前置结尾、相关人物资产、世界规则和直接后续梗概。

### 2. 生成连续故事材料

依据`episode-story-adapter.md`生成`episode-story-materials/<分集编号>.json`：

- 用二至六个连续自然段说明当前场面的起点、人物目标、阻力、调整、即时结果与停止边界。
- 当前集只演自己的变化；直接后续若以同一动作作为主要冲突、核验或选择，当前集只建立前提。
- 不使用清单、证据标签、审核术语或梗概式压缩句。

运行：

```bash
python3 scripts/build_episode_writing_input.py <适配源.json> <连续故事材料.json> <分集编号> --output <缓存目录>/episode-writing-inputs/<分集编号>.txt
```

### 3. Screenwriter原稿

隔离Screenwriter只读取当前写作输入与规定的两个写作Reference，生成`screenplay-drafts/<分集编号>.md`。

原稿必须：

- 形成可以直接阅读和表演的完整场景，而不是梗概或证据清单。
- 让人物通过行动、反馈、迟疑、反驳、接话、关系表达和调整推动局面。
- 首集先自然说明当前处境、重要人物和紧迫任务，再展开冲突。
- 使用`【场景名称·时段·内/外】`、正常叙述段落和`人物：台词`。
- 每集只解决当前主要问题并形成下一压力，停止在冻结边界。
- 不出现制作元话语、内部字段、验证术语、路线条件式说明或未来剧情。

运行：

```bash
python3 scripts/validate_screenwriter_draft.py <缓存目录>/screenplay-drafts/<分集编号>.md --episode-id <分集编号> --receipt <缓存目录>/screenwriter-receipts/<分集编号>.json
```

原稿没有动作—反馈—调整、没有局面变化、含占位或只是百字摘要时不得放行。返修仍只回到当前集原稿，不影响已通过且不相关的分集。

## 写作交接

所有冻结分集都完成原稿和PASS回执后运行：

```bash
python3 scripts/stage_handoff.py writing-create <缓存目录> --pipeline-state <缓存目录>/pipeline-state.json --planning-handoff <缓存目录>/planning-handoff.json --output <缓存目录>/writing-handoff.json
python3 scripts/stage_handoff.py writing-verify <缓存目录> --pipeline-state <缓存目录>/pipeline-state.json --planning-handoff <缓存目录>/planning-handoff.json --writing-handoff <缓存目录>/writing-handoff.json
```

只有实际取得`WRITING_ACCEPTED`和`WRITING_HANDOFF_PASS`才完成写作阶段。随后返回协调者；不得在当前子任务加载校验Skill、正式投影或提前返回部分剧本。

## 用户局部修改

- 拓扑或梗概变化：停止并回到`episode-branch-planner-biz`。
- 梗概不变的剧情表达修改：只重建授权分集的适配材料、写作输入、原稿和回执。
- 只改对白：授权分集的非台词事实、动作、状态、选择和结尾保持不变。
- 修改后旧`writing-handoff.json`立即失效，重新生成交接并进入校验阶段。

## 禁止事项

- 不生成`enhancer-inputs`、`enhanced-screenplays`、正式`episodes`、问题单或验收回执。
- 不修改故事、拓扑、梗概、选择、结局或停止边界。
- 不创建正式业务JSON、完成凭证或工程投影。
- 不创建`work_episode_raw.json`，不在单次写入中批量生成全体正文。
- 不把Skill名、交接文件、原稿回执或内部材料暴露给用户。
