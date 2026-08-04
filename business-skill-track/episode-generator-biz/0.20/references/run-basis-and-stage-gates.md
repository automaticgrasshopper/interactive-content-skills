# 运行基础与阶段门禁

本文件定义私有缓存、阶段依赖和放行条件，不增加正式业务字段。

## 阶段一缓存

### `run-basis.json`

使用合同`nextplay.episode-run-basis.v1`：

```json
{
  "contract_version": "nextplay.episode-run-basis.v1",
  "story": {
    "title": "故事标题",
    "core_goal": "主角必须完成什么",
    "core_conflict": "目标与阻力如何正面冲突",
    "theme": "主题",
    "genre_tone": "题材与基调",
    "world_rules": ["会直接约束剧情的规则"],
    "duration": "体量或时长",
    "node_count_hint": null,
    "required_events": ["用户或上游明确要求保留的事件"],
    "safety_constraints": ["安全限制"],
    "consistency_constraints": ["资产、世界规则或状态连续性要求"]
  },
  "ending_plan": {
    "total": 4,
    "formal": 3,
    "failure": 1,
    "directions": ["各结局的结果和价值方向"]
  },
  "characters": [
    {
      "name": "正式角色名",
      "current_desire": "当前持续欲望",
      "knowledge_boundary": ["当前知道或不知道的关键事实"],
      "capability_boundary": ["能做与不能做的事情"],
      "voice": "说话方式"
    }
  ]
}
```

- `node_count_hint`只记录上游软建议，可为整数、区间字符串或`null`。只有用户明确固定集数时，才把固定数量写入用户意图合同作为硬约束。
- `required_events`只记录用户或正式上游明确要求保留的事件，不把Skill偏好伪装成上游事实。
- `safety_constraints`与`consistency_constraints`允许为空列表，但上游已经提供时必须完整保留。
- `ending_plan.total`必须等于`formal + failure`。没有失败结局时`failure=0`。
- `characters`必须覆盖全部非可选正式角色；每名角色都要冻结欲望、知情边界、能力边界和语言方式。

### `asset-catalog.json`

继续使用`nextplay.episode-assets.v1`：

```json
{
  "contract_version": "nextplay.episode-assets.v1",
  "characters": [],
  "scenes": [],
  "props": [],
  "optional_characters": [],
  "character_aliases": {}
}
```

只登记正式名称；同类不得重名，角色别名不得冲突。上游明确允许不出场的角色才可进入`optional_characters`。

### 阶段一放行

依次运行：

```bash
python3 scripts/validate_user_intent_lock.py contract CACHE_ROOT
python3 scripts/validate_run_basis.py CACHE_ROOT
```

两者退出码均为0且输出PASS，才允许生成情绪脊。

## 阶段二门禁

阶段二依次产生并冻结：

```text
emotional-spine.json
→ story-treatment.json + story-treatment-review.json
→ topology.md
→ episode-synopses/*.json + synopsis-set-review.json
```

情绪脊合同与拓扑格式分别以`emotional-spine-state-graph.md`和`validate_topology.py`为准；完整故事与全体梗概合同以`story-treatment-and-decomposition.md`为准。

依次运行：

```bash
python3 scripts/validate_emotional_spine.py CACHE_ROOT/emotional-spine.json
python3 scripts/story_treatment_gate.py packet CACHE_ROOT --output TREATMENT_PACKET.json
python3 scripts/story_treatment_gate.py seal CACHE_ROOT TREATMENT_REVIEW.json
python3 scripts/story_treatment_gate.py verify CACHE_ROOT
python3 scripts/validate_emotional_topology.py CACHE_ROOT/topology.md --spine CACHE_ROOT/emotional-spine.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_topology.py CACHE_ROOT/topology.md --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_story_topology.py CACHE_ROOT/story-treatment.json CACHE_ROOT/topology.md --expected-endings E
python3 scripts/synopsis_set_gate.py packet CACHE_ROOT --output SYNOPSIS_SET_PACKET.json
python3 scripts/synopsis_set_gate.py seal CACHE_ROOT SYNOPSIS_SET_REVIEW.json
python3 scripts/synopsis_set_gate.py verify CACHE_ROOT
```

必须严格按以上顺序执行。完整故事通过前不得创建正式拓扑；拓扑通过前不得创建梗概；梗概集合通过前不得创建任何完整剧本。脚本负责合同、结构、指纹、映射与证据校验。Agent还必须独立判断全篇因果是否成立、选择是否具有真实价值分歧与持续差异、梗概是否把完整故事均匀拆成可演出的戏剧单位；语义判断不成立时，即使脚本PASS也不得放行。

## 阶段三门禁

全体`episode-synopses/<episode-id>.json`已在阶段二一次生成并由`synopsis-set-review.json`整体冻结。阶段三只建立`episodes/<episode-id>.md`和`quality-reviews/<episode-id>.json`，不得生成、缩写或改写单集梗概。

梗概草案使用私有合同`nextplay.episode-synopsis.v1`：

```json
{
  "contract_version": "nextplay.episode-synopsis.v1",
  "episode_id": "episode-001",
  "title": "冻结标题",
  "synopsis": "只概括本集将实际演出的事件，并自然说清人物问题、变化和下一入口。",
  "conflict": "本集冲突",
  "predecessors": [],
  "successors": ["episode-002"]
}
```

标题、前置和后续必须与冻结拓扑一致。梗概集合门禁通过前，任何完整正文不得存在；当前集未完成`verify-one`前，不得存在其他未放行正文。

阶段三单集固定顺序：

```text
读取冻结梗概 → 完整写作 → 台词复写 → 结构校验 → packet → 独立冷读
→ 返修循环 → seal → verify-one
```

`packet`只生成冷读输入，不代表通过。`seal`只接受问题为空、理解门与全部复检证据齐全、正文、梗概集合和用户意图绑定一致的复检结果。正文变化后必须重新packet、冷读和seal。

所有理解门与复检证据必须逐字存在于对应梗概或正文。当前集直接前置分集的完整回执未通过、发现其他未放行正文、梗概集合回执失效、梗概与正文中的梗概/冲突不一致时，脚本必须拒绝生成完整冷读包。

复检结果使用以下结构；所有摘要值从当前packet逐值复制，判断与证据必须在本次冷读后重新填写：

```json
{
  "script_sha256": "当前packet中的值",
  "reference_sha256": "当前packet中的值",
  "user_intent_source_sha256": "当前packet中的值",
  "user_intent_contract_sha256": "当前packet中的值",
  "synopsis_set_sha256": "当前packet中的值",
  "comprehension": {
    "character_task": {"answer": "复述", "proof": "正文逐字证据"},
    "trigger_cost": {"answer": "复述", "proof": "正文逐字证据"},
    "action_result": {"answer": "复述", "proof": "正文逐字证据"},
    "next_entry": {"answer": "复述", "proof": "正文逐字证据"}
  },
  "covered_checks": ["packet列出的全部八项检查"],
  "evidence": [
    {"check": "普通检查名称", "location": "场次或台词位置", "proof": "正文逐字证据"},
    {
      "check": "普通话表达与叙述可读",
      "dialogue_location": "台词位置",
      "dialogue_proof": "台词逐字证据",
      "narration_location": "叙述位置",
      "narration_proof": "叙述逐字证据"
    },
    {
      "check": "梗概与正文一致",
      "synopsis_proof": "梗概逐字证据",
      "script_proof": "正文逐字证据",
      "explanation": "两处证据如何证明同一事件实际演出"
    }
  ],
  "issues": [],
  "note": "可选说明"
}
```

若冷读发现问题，先把问题写入临时工作记录并返修正文，不得把`issues`强行写成空数组后seal。返修后旧packet失效，必须重新生成。

## 阶段四门禁

阶段四先验证全局用户意图、全路径首次出场和所有当前回执，再调用唯一业务组装器。组装器从冻结拓扑和逐集正文确定性映射九字段JSON，并再次执行全部项目门禁。

完成凭证使用`nextplay.episode-completion.v4`，绑定：

- `run-basis.json`
- `asset-catalog.json`
- `character-introductions.json`
- `emotional-spine.json`
- `story-treatment.json`
- `story-treatment-review.json`
- `topology.md`
- `synopsis-set-review.json`
- `user-request.md`
- `user-intent-lock.json`
- `user-intent-review.json`
- 全部分集正文
- 全部冻结梗概
- 全部逐集回执
- 最终业务JSON

任一绑定文件变化，旧完成凭证立即失效。

## 修改模式

- 局部修改必须提供完整基线缓存，而不是只提供旧业务JSON。
- `--baseline-root`指向修改前缓存。
- 每个允许变化的分集分别传`--allowed-changed episode-xxx`。
- 只改台词时传`--change-scope dialogue`。
- 未授权分集必须逐字不变；局部修改期间`topology.md`必须逐字节不变。
- 局部正文表达或对白修改期间，`story-treatment.json`和全部`episode-synopses/*.json`也必须不变。
- 局部梗概或本集因果修改必须同步维护完整故事对应段落并重跑故事、故事—拓扑和梗概集合门禁；没有用户授权的梗概和正文不得顺带变化。
- 改动正文后，对应逐集回执必须失效并重建；用户要求或用户意图合同变化时，所有受其绑定的回执必须重建。
- 改拓扑时不能使用局部正文模式，必须从阶段二重新执行并重建受影响下游。
