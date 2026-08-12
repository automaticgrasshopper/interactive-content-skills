# 冻结主线、支线生长与分集拆解

## 一、六层材料

1. `mainline-story.json`是拓扑前冻结的单一路线完整故事。
2. `decision-fissure-audit.json`穷举并取舍主线中的真实决定裂缝。
3. `mainline-decomposition.json`先把冻结故事原文切成纯直线主线节点；它先于裂缝和支线。
4. `story-treatment.json`只登记支线生长、选择后果与全部结局，不是另一篇改写后的完整故事，也不是主线梗概来源。
5. `topology.md`在已冻结主线路径上接入支线；`mainline-path.json`保持主线切片与正式节点一一对应。
6. `episode-synopses/*.json`中主线梗概逐字使用冻结故事切片，支线梗概使用支线事实。
7. 分集正文只改编对应梗概，不反向改故事或拓扑。

## 二、冻结主线合同

`mainline-story.json`使用`nextplay.episode-mainline-story.v1`：

```json
{
  "contract_version": "nextplay.episode-mainline-story.v1",
  "title": "故事标题",
  "complete_story": "从开场连续写到期待性正式结局的完整可读故事",
  "expected_ending_title": "期待性正式结局标题"
}
```

`complete_story`必须像已经发生过的一篇完整故事：只写确定行动、阻力、后果、关系变化、关键真相与最终结算。不得出现“如果、或者、另一条路线、玩家可以、选择A/B”等分支可能性语言，不得提前编号分集。它必须完整承载核心目标、主要人物变化、全部必保事件与期待性类型兑现。

主线是全图最完整的一条原始路线，不是最短路线，也不是最长路线的上限。后续允许其他路线与它等长或更长，只要未超过上游单次游戏时长。冻结后任何支线都不得改写主线已经发生的因果。

`mainline_story_gate.py packet`提供主线盲读包。复检必须绑定哈希，分别复述主角目标、连续因果、必保事件和期待性结局，并为“上游事实、人物动机与知情边界、连续因果、关键真相、必保事件、期待性类型兑现”逐项给出主线逐字证据。`issues`为空才可seal。

## 三、纯直线主线先行

主线通过后先执行`references/mainline-first-topology.md`。不得先写支线故事图再回头决定主线分集数量。选择只会把原主线行动降级为一个选项；选择后的原文从下一主线节点继续，不得被支线材料重述。

## 四、决策裂缝审计

`decision-fissure-audit.json`使用`nextplay.decision-fissure-audit.v2`。根对象必须逐字复制`stage-two-input.json`的`core_goal`并给出主线证据。从冻结主线开场扫描到结局，每个候选记录主线逐字位置、决定问题、至少两个可执行且互斥动作、即时后果、核心目标状态、路线是否结束、`ending_scope`、对照原始核心目标的解释和理由。

候选只能标记`adopt`或`reject-causally-insufficient`。继续路线的`ending_scope`为`none`；正好兑现上游主要结局方向的结束动作为`main`；其余提前终止为`minor`。不得用部分证据、人员安全或继续追查等新目标替换冻结核心目标。明确交易必须同时列出真实服从与拒绝。

## 五、支线事实登记合同

`story-treatment.json`使用`nextplay.episode-story-treatment.v4`。`endings`只记录上游预算内的主要结局；`minor_endings`动态记录独立小结局：

```json
{
  "contract_version": "nextplay.episode-story-treatment.v4",
  "title": "故事标题",
  "mainline_sha256": "冻结mainline-story.json的规范化哈希",
  "decision_fissure_audit_sha256": "已通过裂缝审计的规范化哈希",
  "minor_endings": [{"title":"独立标题","kind":"minor","source_action_id":"action-001","causal_payoff":"动作如何直接终止路线"}],
  "complete_story": "为兼容合同保留的路线事实登记；不得作为主线节点或主线梗概来源",
  "choices": [
    {
      "choice_id": "choice-001",
      "dramatic_cause": "为何此刻真的必须决定",
      "question": "玩家面对的问题",
      "options": [
        {
          "option_id": "A",
          "option_text": "动词＋明确对象",
          "immediate_consequence": "立即发生的不同后果",
          "lasting_difference": "若尚未结束，后续持续承接的差异；已结束则写结局状态"
        }
      ],
      "merge_or_ending": "各路线继续、带差异汇合或结束的因果理由"
    }
  ],
  "endings": [
    {"title": "结局标题", "kind": "formal或failure", "causal_payoff": "此前动作如何造成结局"}
  ]
}
```

支线生成顺序固定：

1. 扫描冻结主线中的真实决定裂缝，不凭互动数量先造空树。
2. 为每个选项先写不同且可见的即时后果。
3. 即时后果发生后，先判断该路线是否已形成因果充分、情绪完成的结局。
4. 已结束路线立即停止，不再承担主线尚未发生的必保事件。
5. 未结束路线才继续生长、再次选择或带差异汇合；每条新路线都重新扫描自己的真实裂缝。

支线可短于、等于或长于主线。主线只决定一条原始完整路线，不控制其他路线的节点数。分支结束与否由当前行动及其已明确风险决定；不得为了让所有路线经历相同事件而拖延小结局，也不得为了做短路线把未结算冲突砍成结果提示。

故事图复检必须检查主线哈希绑定、选择原因、即时后果、路线继续/终止判断、持续差异、汇合承接、全部结局因果回收与类型兑现。拓扑只能投影已通过的故事图，不能新增选择或结局。

## 六、拓扑与路线分钟数

拓扑把每条路线展开成不可再合并的可演戏剧单位，然后才统计和编号节点。最短合法结局路径固定为2个有完整剧情的节点：第一节点建立风险并作出选择，第二节点完整演出后果与结局。

`route-duration.json`使用`nextplay.route-duration.v1`：

```json
{
  "contract_version": "nextplay.route-duration.v1",
  "unit": "minutes",
  "duration_limit_minutes": 50,
  "mainline_path": ["episode-001", "episode-004", "episode-009"],
  "node_minutes": {"episode-001": 4.0},
  "paths": [
    {"ending_id": "episode-009", "node_ids": ["episode-001", "episode-004", "episode-009"], "total_minutes": 12.0}
  ]
}
```

`mainline_path`必须是一条真实的入口到正式结局路线，使冻结主线在全图中可辨认。`paths`必须精确枚举全部入口到结局路线；每条总分钟数等于沿途节点预计分钟数之和，且不得超过上游单次游戏时长。主线路径不是其他路线的上限，节点数也不作为时长代理。

## 七、分集梗概合同

每个`episode-synopses/<episode-id>.json`只含：

```json
{
  "contract_version": "nextplay.episode-synopsis.v1",
  "episode_id": "episode-001",
  "title": "冻结标题",
  "synopsis": "处境与目标；行动、阻力与调整；结果与下一入口。",
  "conflict": "本集可演出的核心冲突",
  "predecessors": [],
  "successors": ["episode-002"]
}
```

标题、前置、后续必须与拓扑完全一致。每集梗概至少完成一次状态变化；选择集必须停在玩家选择，选择结果由后继节点演出；结局集必须完整结算。

`synopsis_set_gate.py packet`提供支线故事图、拓扑和全部梗概。复检结果沿用脚本给出的哈希字段，并包含：

```json
{
  "comprehension": {
    "overall_causal_progression": {"answer": "全图因果复述", "proof": "故事逐字证据"},
    "route_continuity": {"answer": "路线连续性复述", "proof": "故事或梗概逐字证据"},
    "ending_payoffs": {"answer": "结局回收复述", "proof": "故事或梗概逐字证据"}
  },
  "episode_checks": [
    {
      "episode_id": "episode-001",
      "situation_goal_proof": "梗概逐字证据",
      "action_resistance_adjustment_proof": "梗概逐字证据",
      "result_next_entry_proof": "梗概逐字证据",
      "treatment_source_proof": "支线故事图逐字证据"
    }
  ],
  "covered_checks": [],
  "evidence": [],
  "issues": []
}
```

每个冻结节点必须且只能出现一条`episode_checks`。集合门禁通过后，任一主线、支线故事、拓扑、路线时长或梗概变化都会使下游失效。全体梗概冻结前不得创建任何完整剧本。
