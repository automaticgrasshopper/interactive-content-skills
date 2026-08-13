# 运行基础与阶段门禁

本文件定义私有缓存、阶段依赖和放行条件，不增加正式业务字段。

## 阶段一缓存

### `run-basis.json`

使用合同`nextplay.episode-run-basis.v2`：

```json
{
  "contract_version": "nextplay.episode-run-basis.v2",
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
      "identity": "观众首次见到时必须知道的正式身份",
      "relationships": ["与正式角色、组织或当前任务的明确关系"],
      "current_desire": "当前持续欲望",
      "knowledge_boundary": ["当前知道或不知道的关键事实"],
      "capability_boundary": ["能做与不能做的事情"],
      "voice": "说话方式"
    }
  ]
}
```

- `node_count_hint`只记录上游软建议，可为整数、区间字符串或`null`。它只用于来源追溯，不进入阶段二生成包，也不在正式拓扑冻结前参与比较、压缩或扩展。只有用户明确固定集数时，才把固定数量写入用户意图合同作为硬约束。
- `required_events`只记录用户或正式上游明确要求保留的事件，不把Skill偏好伪装成上游事实。
- `safety_constraints`与`consistency_constraints`允许为空列表，但上游已经提供时必须完整保留。
- `ending_plan.total`必须等于`formal + failure`。没有失败结局时`failure=0`。
- `ending_plan.directions`至少有一项明确写出核心目标与主要类型承诺如何得到正面兑现，作为期待性正式结局；不能全部是反讽、遗憾、开放或失败方向。
- `genre_tone`、世界规则或核心冲突已经建立可信致命风险，且玩家错误可以因果性触发时，`failure`不得为零，方向中至少包含死亡或同等不可逆失败。无致命风险时不强制死亡。
- `characters`必须覆盖全部非可选正式角色；每名角色都要从上游原样冻结一条简明`identity`、至少一条`relationships`，以及欲望、知情边界、能力边界和语言方式。地点和当前动作不是身份或关系。

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

两者退出码均为0且输出PASS后，运行`build_stage_two_input.py`生成`stage-two-input.json`。该临时包必须省略`node_count_hint`；阶段二生成期间不得直接读取`run-basis.json`、`user-request.md`、原始上游输入、旧拓扑、旧情绪脊、旧梗概或旧正文。只有用户意图合同中的固定集数硬约束可以进入生成包。

## 阶段二门禁

阶段二依次产生并冻结：

```text
stage-two-input.json
→ unnumbered-emotional-movement.json
→ story-treatment.json + story-treatment-review.json
→ topology.md
→ emotional-spine.json
→ episode-synopses/*.json + synopsis-set-review.json
```

情绪脊合同与拓扑格式分别以`emotional-spine-state-graph.md`和`validate_topology.py`为准；完整故事与全体梗概合同以`story-treatment-and-decomposition.md`为准。

依次运行：

```bash
python3 scripts/build_stage_two_input.py CACHE_ROOT --output CACHE_ROOT/stage-two-input.json
python3 scripts/validate_emotional_movement.py CACHE_ROOT/unnumbered-emotional-movement.json
python3 scripts/story_treatment_gate.py packet CACHE_ROOT --output TREATMENT_PACKET.json
python3 scripts/story_treatment_gate.py seal CACHE_ROOT TREATMENT_REVIEW.json
python3 scripts/story_treatment_gate.py verify CACHE_ROOT
python3 scripts/validate_topology.py CACHE_ROOT/topology.md --movement CACHE_ROOT/unnumbered-emotional-movement.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_story_topology.py CACHE_ROOT/story-treatment.json CACHE_ROOT/topology.md --expected-endings E
python3 scripts/validate_emotional_spine.py CACHE_ROOT/emotional-spine.json
python3 scripts/validate_emotional_topology.py CACHE_ROOT/topology.md --spine CACHE_ROOT/emotional-spine.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/synopsis_set_gate.py packet CACHE_ROOT --output SYNOPSIS_SET_PACKET.json
python3 scripts/synopsis_set_gate.py seal CACHE_ROOT SYNOPSIS_SET_REVIEW.json
python3 scripts/synopsis_set_gate.py verify CACHE_ROOT
```

必须严格按以上顺序执行。未编号情绪运动合同通过前不得写完整故事；完整故事通过前不得创建正式编号拓扑；路线级拓扑完成前不得确定全图节点数；正式拓扑通过前不得生成逐节点情绪脊或梗概；梗概集合通过前不得创建任何完整剧本。重新生成阶段二时必须从未编号情绪运动开始，既有节点、边、标题、分集顺序和分支形状全部视为无效下游产物。脚本负责合同、结构、指纹、映射与证据校验。Agent还必须独立判断全篇因果是否成立、所有结局路径是否至少包含2个有完整剧情的节点、提前小结局是否由选择前已明确的风险和玩家动作充分造成、正式路线目标体量是否没有被全图节点数压缩、各重大路线是否重新扫描过后续裂缝、类型期待是否至少被一个正式结局正面兑现、致命风险是否得到相称的失败结局、选择是否具有真实价值分歧与持续差异、梗概是否把完整故事均匀拆成可演出的戏剧单位；语义判断不成立时，即使脚本PASS也不得放行。

## 阶段三门禁

全体`episode-synopses/<episode-id>.json`已在阶段二一次生成并由`synopsis-set-review.json`整体冻结。阶段三为当前集建立适配源、连续故事材料、写作输入、Screenwriter草稿、Enhancer增强稿及写后回执；正式正文直接使用增强稿，不得再生成第三版正文，也不得生成、缩写或改写单集梗概。全部中间材料都是私有文件，不增加正式业务字段。

阶段三先按冻结拓扑划分工作批次，每批最多3个相邻因果节点；共同主线、互斥分支、汇合段和结局段不得混成一个活跃工作集。批次不产生新业务字段，也不允许批量抢跑正文。编剧与Enhancer优先使用彼此隔离的工作区；没有隔离能力时也必须严格换档。批内仍执行“一集写作、一集增强、一集只读验收、一集冷读、一集放行”。

有限工作集是Agent执行约束，不是新增的脚本合同。脚本不能证明模型是否重新关注了旧上下文；脚本继续负责拒绝抢跑正文、无效前置回执、失效梗概集合和未通过的当前集。不得把工作集说明写成脚本已经提供的隔离能力。

每集开始时先生成适配源；适配者比较当前梗概与直接后续梗概，写成连续故事和一句停止边界。Screenwriter只能看连续故事输入；Enhancer只能看当前草稿、停止边界和Enhancer reference。更早正文、过程计划、旧审稿记录、无关路线和验收答案不得进入两者的工作区。

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
适配源 → 连续故事材料 → 材料门禁 → Screenwriter草稿 → Enhancer增强稿
→ 增强稿原样成为正式正文候选 → 只读结构校验 → 写后过程计划 → plan门禁
→ 场面展开packet → 逐拍完成度复检 → seal → verify-one
→ 含停止边界的独立冷读packet → 只读冷读结论 → seal → verify-one
```

场面展开计划必须在最终正文完成后，独立依据冻结梗概建立；生成计划时不得读取草稿、连续故事材料或验收答案。计划完整且无重复地覆盖梗概原文，关键事件写明起始状态、至少两个可见步骤、结束状态和状态变化。`dramatization_gate.py packet`只生成逐拍复检输入，不代表通过。

场面展开通过后才生成独立冷读`packet`。冷读包不得包含过程计划，但必须包含当前停止边界与直接后续梗概摘录，用于检查抢写；它不能读取后续正文。`episode_quality_gate.py seal`只接受问题为空、理解门、相邻边界与全部复检证据齐全的结果。正文变化后两类回执都失效。

结构校验PASS后必须执行一次判断依据换档：冷读结论只允许引用脚本生成的当前`packet`和`episode-quality-review.md`，不得引用写作笔记、作者计划、预期答案或后续剧情替正文辩护。同一 Agent 可以继续执行；冷读登记问题后，才允许重新读取当前集返修所需的写作材料。

所有理解门与复检证据必须逐字存在于对应梗概或正文。当前集场面展开回执未通过、直接前置分集的完整回执未通过、发现其他未放行正文、梗概集合回执失效、梗概与正文中的梗概/冲突不一致时，脚本必须拒绝生成完整冷读包。

复检结果使用以下结构；所有摘要值从当前packet逐值复制，判断与证据必须在本次冷读后重新填写：

```json
{
  "script_sha256": "当前packet中的值",
  "reference_sha256": "当前packet中的值",
  "user_intent_source_sha256": "当前packet中的值",
  "user_intent_contract_sha256": "当前packet中的值",
  "synopsis_set_sha256": "当前packet中的值",
  "story_material_sha256": "当前packet中的值",
  "comprehension": {
    "character_task": {"answer": "复述", "proof": "正文逐字证据"},
    "trigger_cost": {"answer": "复述", "proof": "正文逐字证据"},
    "action_result": {"answer": "复述", "proof": "正文逐字证据"},
    "next_entry": {"answer": "复述", "proof": "正文逐字证据"}
  },
  "covered_checks": ["packet列出的全部九项检查"],
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
    },
    {
      "check": "相邻分集边界",
      "script_stop_proof": "当前集停止画面逐字证据",
      "successor_proof": "直接后续梗概中的独占动作；结局集写无后续分集",
      "explanation": "为什么当前正文没有提前完成后续动作"
    }
  ],
  "issues": [],
  "note": "可选说明"
}
```

若结构验收或冷读发现问题，把问题写入临时工作记录并停止当前集放行；不得自动改写正文，也不得把`issues`强行写成空数组后seal。以后若用户明确要求另写新稿，新稿必须保存为新的Screenwriter产物，并使旧packet与回执失效。

## 阶段四门禁

阶段四先验证全局用户意图、全路径首次出场和所有当前回执，再调用唯一业务组装器。组装器从冻结拓扑和逐集正文确定性映射九字段JSON，并再次执行全部项目门禁。

完成凭证使用`nextplay.episode-completion.v6`，绑定：

- `run-basis.json`
- `unnumbered-emotional-movement.json`
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
- 全部适配源、连续故事材料、编剧输入和编剧草稿
- 全部场面展开计划
- 全部场面展开复检回执
- 全部逐集回执
- 最终业务JSON

任一绑定文件变化，旧完成凭证立即失效。

## 修改模式

- 先区分内部返修与用户局部编辑。Agent为修正首次生成结果而改变故事或拓扑时，仍从最早失效阶段重跑；用户已经在现有分集结果上新增、插入、修改、删除或重连节点时，读取`local-node-editing.md`，以用户操作后的当前节点关系为事实源，不重新生成情绪脊或全局拓扑。
- 九字段业务结果的受控局部修改必须提供完整基线缓存，而不是只提供旧业务JSON。工程侧局部编辑由调用方提供目标节点、直接前置、直接后续和相关人物资产即可；工程route只作定位上下文，不进入本节业务缓存合同。
- `--baseline-root`指向修改前缓存。
- 每个允许变化的分集分别传`--allowed-changed episode-xxx`。
- 只改台词时传`--change-scope dialogue`。
- 未授权分集必须逐字不变；局部修改期间`topology.md`必须逐字节不变。
- 局部正文表达或对白修改期间，`story-treatment.json`和全部`episode-synopses/*.json`也必须不变。
- 局部梗概或本集因果修改必须同步维护完整故事对应段落并重跑故事、故事—拓扑和梗概集合门禁；没有用户授权的梗概和正文不得顺带变化。
- 改动正文后，对应逐集回执必须失效并重建；用户要求或用户意图合同变化时，所有受其绑定的回执必须重建。
- 非用户局部编辑导致的内部拓扑返修不能使用局部正文模式，必须从阶段二重新执行并重建受影响下游。用户明确执行的局部结构编辑只重建授权节点内容和受影响接缝；工程图的字段写回、稳定节点引用和边更新由调用方适配层负责，不改本Skill九字段业务合同。
