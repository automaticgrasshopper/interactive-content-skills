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

阶段二产生`emotional-spine.json`与`topology.md`。情绪脊合同、字段和拓扑格式分别以`emotional-spine-state-graph.md`与`validate_topology.py`解析格式为准。

依次运行：

```bash
python3 scripts/validate_emotional_topology.py CACHE_ROOT/topology.md --spine CACHE_ROOT/emotional-spine.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_topology.py CACHE_ROOT/topology.md --expected-endings E --expected-formal F --expected-failure X
```

脚本负责确定性结构校验。Agent还必须逐一判断选择是否具有真实价值分歧、代价、即时结果和后续差异；语义判断不成立时，即使脚本PASS也不得放行。

## 阶段三门禁

每集正文使用`episodes/<episode-id>.md`，每集回执使用`quality-reviews/<episode-id>.json`。不得先批量写完再补回执。

单集固定顺序：

```text
写作 → 台词复写 → 结构校验 → packet → 独立冷读 → 返修循环 → seal → verify-one
```

`packet`只生成冷读输入，不代表通过。`seal`只接受问题为空、理解门与七项证据齐全、指纹和用户意图绑定一致的复检结果。正文变化后必须重新packet、冷读和seal。

复检结果使用以下结构；所有摘要值从当前packet逐值复制，判断与证据必须在本次冷读后重新填写：

```json
{
  "script_sha256": "当前packet中的值",
  "reference_sha256": "当前packet中的值",
  "user_intent_source_sha256": "当前packet中的值",
  "user_intent_contract_sha256": "当前packet中的值",
  "comprehension": {
    "character_task": {"answer": "复述", "proof": "正文逐字证据"},
    "trigger_cost": {"answer": "复述", "proof": "正文逐字证据"},
    "action_result": {"answer": "复述", "proof": "正文逐字证据"},
    "next_entry": {"answer": "复述", "proof": "正文逐字证据"}
  },
  "covered_checks": ["packet列出的全部七项检查"],
  "evidence": [
    {"check": "普通检查名称", "location": "场次或台词位置", "proof": "正文逐字证据"},
    {
      "check": "普通话表达与叙述可读",
      "dialogue_location": "台词位置",
      "dialogue_proof": "台词逐字证据",
      "narration_location": "叙述位置",
      "narration_proof": "叙述逐字证据"
    }
  ],
  "issues": [],
  "note": "可选说明"
}
```

若冷读发现问题，先把问题写入临时工作记录并返修正文，不得把`issues`强行写成空数组后seal。返修后旧packet失效，必须重新生成。

## 阶段四门禁

阶段四先验证全局用户意图、全路径首次出场和所有当前回执，再调用唯一业务组装器。组装器从冻结拓扑和逐集正文确定性映射九字段JSON，并再次执行全部项目门禁。

完成凭证使用`nextplay.episode-completion.v2`，绑定：

- `run-basis.json`
- `asset-catalog.json`
- `character-introductions.json`
- `emotional-spine.json`
- `topology.md`
- `user-request.md`
- `user-intent-lock.json`
- `user-intent-review.json`
- 全部分集正文
- 全部逐集回执
- 最终业务JSON

任一绑定文件变化，旧完成凭证立即失效。

## 修改模式

- 局部修改必须提供完整基线缓存，而不是只提供旧业务JSON。
- `--baseline-root`指向修改前缓存。
- 每个允许变化的分集分别传`--allowed-changed episode-xxx`。
- 只改台词时传`--change-scope dialogue`。
- 未授权分集必须逐字不变；局部修改期间`topology.md`必须逐字节不变。
- 改动正文后，对应逐集回执必须失效并重建；用户要求或用户意图合同变化时，所有受其绑定的回执必须重建。
- 改拓扑时不能使用局部正文模式，必须从阶段二重新执行并重建受影响下游。
