---
name: episode-branch-planner-biz
description: "当游戏企划、角色描述、场景描述和道具描述已经齐备，用户要求生成或修改互动影游的完整故事、分集拓扑、情绪脊、选择、分支、汇合、结局或全体分集梗概时，使用本 Skill。普通用户任务中它先担任三阶段协调入口，必须把规划、逐集写作和最终校验依次派给三个全新子任务；带 STAGE_WORKER:planning 标记时才在当前上下文生成并冻结规划。节点增删、移动、重连及选择或结局修改也从此进入。"
---

# 分支规划师

## 目标

普通用户任务先按三阶段合同担任协调者；只有带`STAGE_WORKER:planning`标记并持有合法阶段票据的全新子任务，才把四项上游输入转成完整故事、自然情绪脊、正式分支图和全体分集梗概。

本 Skill不写分集正文，不执行Enhancer，不组装九字段业务JSON。完整读取`references/split-pipeline-contract.md`后，先判断协调者模式或规划子任务模式。

## 协调者入口

当前任务没有`STAGE_WORKER:planning`时，不得读取规划Reference或生成任何故事内容。按`split-pipeline-contract.md`初始化流水线，依次使用子任务调度工具创建三个全新阶段子任务。每个子任务返回后先执行确定性交接验收，最后取得`PROJECTION_AUTHORIZED`才允许正式投影。

不得在协调者上下文加载剧本创作师或剧本校验师的正文；它们只能由对应全新子任务加载。

## 规划子任务入口

只有提示中存在`STAGE_WORKER:planning`、缓存目录和规划票据路径时才进入以下规划流程。首先运行：

```bash
python3 scripts/pipeline_guard.py claim planning --state <缓存目录>/pipeline-state.json --ticket <规划票据.json>
```

未取得`PLANNING_WORKER_CLAIMED`立即停止，不自行转成协调者或写作阶段。

## 输入

初次生成必须同时具备：

1. 游戏企划
2. 角色描述
3. 场景描述
4. 道具描述

进入阶段前依次读取：

- `references/business-interface.md`
- `references/episode-output-schema.md`
- `references/upstream-input-translation.md`
- `references/user-intent-lock.md`
- `references/run-basis-and-stage-gates.md`

缺少哪一项只追问哪一项。用户要求是创作硬约束，优先于上游建议和内部启发式；用户要求互相冲突时才暂停询问。

## 规划原则

- 先生成不带分集编号和拓扑形状的情绪运动，再写完整可读故事；不得先按节点预算画图。
- 第一版可读故事只接收六组必要材料：标题、核心事件、故事硬边界、必保事实、必要人物与资产、期待性兑现。设定随人物行动按需出现。
- 可读故事冻结后才扫描真实决定裂缝、设计支线和拓扑。主线分集梗概逐字等于可读故事对应切片。
- 强制生成两版图形结构不同的完整拓扑，只允许第二版进入后续。
- 分支必须演出选择后的不同事实；取得共同事实后才允许带差异汇合。
- 主要结局不得做成末端结局菜单；至少两个独立小结局来自不同真实决定裂缝。
- 路径展开量与全图节点数分开；允许二级开扇、长距离分线、非对称路线和多种汇合形状。
- 冻结拓扑后生成逐节点情绪脊，再一次性生成并整体复检全部梗概。
- 题材只提供不超过三项场面承诺，不建立第二套结构规则。

## 初次生成流程

### 1. 冻结运行基础

保存`user-request.md`，生成：

- `user-intent-lock.json`
- `run-basis.json`
- `asset-catalog.json`
- `character-introductions.json`

运行：

```bash
python3 scripts/validate_user_intent_lock.py contract <缓存目录>
python3 scripts/validate_run_basis.py <缓存目录>
python3 scripts/build_stage_two_input.py <缓存目录> --output <缓存目录>/stage-two-input.json
```

全部PASS后进入故事规划。

### 2. 完整故事

按顺序读取：

1. `references/emotional-spine-state-graph.md`
2. `references/mainline-story-writing.md`
3. `references/story-treatment-and-decomposition.md`
4. `references/mainline-first-topology.md`
5. `references/genre-direction.md`

先生成并验证：

- `unnumbered-emotional-movement.json`
- `mainline-story-input.json`
- `mainline-story.json`
- `mainline-story-review.json`

```bash
python3 scripts/validate_emotional_movement.py <缓存目录>/unnumbered-emotional-movement.json --stage-two-input <缓存目录>/stage-two-input.json
python3 scripts/validate_mainline_story_input.py <缓存目录>
python3 scripts/mainline_story_gate.py packet <缓存目录> --output <主线复检包.json>
python3 scripts/mainline_story_gate.py seal <缓存目录> <主线复检结果.json>
python3 scripts/mainline_story_gate.py verify <缓存目录>
```

可读故事必须从开场到期待性正式结局连续可读，不出现路线、节点或“可能选择”的措辞。

### 3. 裂缝、支线与拓扑

把主线原文无遗漏切成`mainline-decomposition.json`并先运行：

```bash
python3 scripts/validate_mainline_projection.py <缓存目录> --decomposition-only
```

随后生成并复检：

- `decision-fissure-audit.json`
- `decision-fissure-review.json`
- `story-treatment.json`
- `story-treatment-review.json`
- `topology-draft-1.md`
- `topology.md`
- `mainline-path.json`
- `route-duration.json`
- `emotional-spine.json`

运行原0.46对应门禁：

```bash
python3 scripts/decision_fissure_gate.py packet <缓存目录> --output <裂缝复检包.json>
python3 scripts/decision_fissure_gate.py seal <缓存目录> <裂缝复检结果.json>
python3 scripts/decision_fissure_gate.py verify <缓存目录>
python3 scripts/story_treatment_gate.py packet <缓存目录> --output <故事复检包.json>
python3 scripts/story_treatment_gate.py seal <缓存目录> <故事复检结果.json>
python3 scripts/story_treatment_gate.py verify <缓存目录>
python3 scripts/validate_topology_revision.py <缓存目录>/topology-draft-1.md <缓存目录>/topology.md
python3 scripts/validate_topology.py <缓存目录>/topology.md --movement <缓存目录>/unnumbered-emotional-movement.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_story_topology.py <缓存目录>/story-treatment.json <缓存目录>/topology.md --expected-endings E
python3 scripts/validate_route_duration.py <缓存目录>/route-duration.json <缓存目录>/topology.md <缓存目录>/stage-two-input.json
python3 scripts/validate_emotional_spine.py <缓存目录>/emotional-spine.json
python3 scripts/validate_emotional_topology.py <缓存目录>/topology.md --spine <缓存目录>/emotional-spine.json --expected-endings E --expected-formal F --expected-failure X
```

`E`、`F`、`X`分别是上游主要结局总数、正式数和失败数；独立小结局不计入三者。

### 4. 全体梗概与规划交接

完整读取`references/story-to-episode-synopsis.md`，一次生成全部`episode-synopses/<episode-id>.json`和`synopsis-set-review.json`，运行：

```bash
python3 scripts/synopsis_set_gate.py packet <缓存目录> --output <梗概复检包.json>
python3 scripts/synopsis_set_gate.py seal <缓存目录> <梗概复检结果.json>
python3 scripts/synopsis_set_gate.py verify <缓存目录>
python3 scripts/stage_handoff.py planning-create <缓存目录> --pipeline-state <缓存目录>/pipeline-state.json --output <缓存目录>/planning-handoff.json
python3 scripts/stage_handoff.py planning-verify <缓存目录> --pipeline-state <缓存目录>/pipeline-state.json --planning-handoff <缓存目录>/planning-handoff.json
```

只有实际取得`PLANNING_ACCEPTED`和`PLANNING_HANDOFF_PASS`才冻结规划。随后返回协调者；不得在当前子任务加载写作Skill、返回正式结果或写入项目路线。

## 用户修改

已有结果上发生节点增删、移动、重连或结构修改时，完整读取`references/canvas-current-state.md`和`references/local-node-editing.md`。重新读取当前全部节点和边，运行`validate_canvas_snapshot.py`定位目标及直接前后集。

用户修改是事实源，不用情绪脊反驳或优化。只在关键人物生死、身份、关系、世界规则、选择去向或下一集成立条件迫使相邻集改变时，询问是否扩大修改范围。修改后使受影响规划交接失效，重新生成并验证规划交接，再进入剧本创作阶段。

## 禁止事项

- 不写`screenplay-drafts`、`enhanced-screenplays`或`episodes`。
- 不创建`episode-business.json`、完成凭证或正式投影。
- 不创建`work_episode_raw.json`或一次性批量正文。
- 不因工作量、节点多或一次只完成一集而停止。
- 不把内部故事、拓扑、情绪脊、梗概、回执或哈希暴露给用户。
