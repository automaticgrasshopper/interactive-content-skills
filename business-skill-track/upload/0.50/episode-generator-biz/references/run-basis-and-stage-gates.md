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
    "duration": "仅供来源追溯的体量或时长；缺失时为null",
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
- `characters`必须覆盖全部非可选正式角色；每名角色都要冻结一条简明`identity`、至少一条`relationships`，以及欲望、知情边界、能力边界和语言方式。`identity`首先写观众可自然得知的公开身份；确需保留内部戏剧功能时只能在中文分号`；`后登记，分号后的内容不得进入首次出场要求或自然台词。地点和当前动作不是身份或关系。

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

两者退出码均为0且输出PASS后，运行`build_stage_two_input.py`生成`stage-two-input.json`。该临时包必须省略`node_count_hint`和`duration`；阶段二生成期间不得直接读取`run-basis.json`、`user-request.md`、原始上游输入、旧拓扑、旧情绪脊、旧梗概或旧正文。不得因缺少单条路线分钟数向用户提问。只有用户意图合同中的固定集数硬约束可以进入生成包。

## 阶段二门禁

阶段二依次产生并冻结：

```text
stage-two-input.json
→ unnumbered-emotional-movement.json
→ mainline-story-input.json（只含六组可读故事材料）
→ mainline-story.json + mainline-story-review.json
→ decision-fissure-audit.json + decision-fissure-review.json
→ story-treatment.json + story-treatment-review.json
→ topology-draft-1.md（必须丢弃的第一版）
→ topology.md（与第一版形状不同的唯一正式第二版）
→ route-duration.json
→ emotional-spine.json
→ episode-synopses/*.json + synopsis-set-review.json
```

情绪脊合同与拓扑格式分别以`emotional-spine-state-graph.md`和`validate_topology.py`为准；完整故事与全体梗概合同以`story-treatment-and-decomposition.md`为准。

依次运行：

```bash
python3 scripts/build_stage_two_input.py CACHE_ROOT --output CACHE_ROOT/stage-two-input.json
python3 scripts/validate_emotional_movement.py CACHE_ROOT/unnumbered-emotional-movement.json --stage-two-input CACHE_ROOT/stage-two-input.json
python3 scripts/validate_mainline_story_input.py CACHE_ROOT
python3 scripts/mainline_story_gate.py packet CACHE_ROOT --output MAINLINE_PACKET.json
python3 scripts/mainline_story_gate.py seal CACHE_ROOT MAINLINE_REVIEW.json
python3 scripts/mainline_story_gate.py verify CACHE_ROOT
python3 scripts/validate_mainline_projection.py CACHE_ROOT --decomposition-only
python3 scripts/decision_fissure_gate.py packet CACHE_ROOT --output FISSURE_PACKET.json
python3 scripts/decision_fissure_gate.py seal CACHE_ROOT FISSURE_REVIEW.json
python3 scripts/decision_fissure_gate.py verify CACHE_ROOT
python3 scripts/story_treatment_gate.py packet CACHE_ROOT --output TREATMENT_PACKET.json
python3 scripts/story_treatment_gate.py seal CACHE_ROOT TREATMENT_REVIEW.json
python3 scripts/story_treatment_gate.py verify CACHE_ROOT
python3 scripts/validate_topology.py CACHE_ROOT/topology.md --movement CACHE_ROOT/unnumbered-emotional-movement.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_topology_revision.py CACHE_ROOT/topology-draft-1.md CACHE_ROOT/topology.md
python3 scripts/validate_story_topology.py CACHE_ROOT/story-treatment.json CACHE_ROOT/topology.md --expected-endings E
python3 scripts/validate_route_duration.py CACHE_ROOT/route-duration.json CACHE_ROOT/topology.md
python3 scripts/repair_mainline_projection.py CACHE_ROOT --apply --report CACHE_ROOT/mainline-projection-repair.json
python3 scripts/validate_mainline_projection.py CACHE_ROOT --topology-only
python3 scripts/validate_emotional_spine.py CACHE_ROOT/emotional-spine.json
python3 scripts/validate_emotional_topology.py CACHE_ROOT/topology.md --spine CACHE_ROOT/emotional-spine.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_mainline_projection.py CACHE_ROOT --review-packet > MAINLINE_PROJECTION_PACKET.json
python3 scripts/repair_mainline_projection.py CACHE_ROOT --apply --report CACHE_ROOT/mainline-projection-repair.json
python3 scripts/validate_mainline_projection.py CACHE_ROOT
python3 scripts/synopsis_set_gate.py packet CACHE_ROOT --output SYNOPSIS_SET_PACKET.json
python3 scripts/synopsis_set_gate.py seal CACHE_ROOT SYNOPSIS_SET_REVIEW.json
python3 scripts/synopsis_set_gate.py verify CACHE_ROOT
```

必须严格按以上顺序执行。情绪运动通过后先冻结六组可读故事输入；故事写作只读取该输入，不读取完整企划、完整资产或任何结构规划。主线冷读通过前不得创建切片或生长支线，主线分解门禁通过前不得扫描裂缝，支线故事图通过前不得编号拓扑。必须先完成未编号全图，再按从入口向右、同层按选项从上到下的稳定顺序统一编号；禁止先编号主线再追加支线。拓扑与路线记账完成后先校验连续映射，再用独立事件归属复检逐节点核对切片的开场、转折和收束；安全修复只整理映射、路径记账和逐字梗概，不添加边、不改故事，也不得在缺少有效事件归属回执时覆盖梗概。全体梗概完成后再次校验逐字映射与事件归属，随后才允许封存梗概集合。Agent还必须判断：主线是否完整且可连续阅读；人物与设定是否随事件按需进入；每个选项即时后果后是否先做结束判断；提前结局是否因果充分；是否至少形成2个不占主要预算的独立小结局；人物偏离核心故事且无合理回归动力时是否及时停止；未结束路线是否继续扫描裂缝；主线路径是否可辨认但不限制其他路线长度；所有结局路径是否至少2个有完整剧情的节点。评论性判断在两次局部修复后仍无确定结论时可记录告警后放行；结构断路、错误跳转、结局类型、哈希和正式字段合同错误不得豁免。

## 阶段三门禁

全体`episode-synopses/<episode-id>.json`已在阶段二一次生成并由`synopsis-set-review.json`整体冻结。阶段三为当前集建立适配源、连续故事材料、写作输入、Screenwriter草稿、Enhancer唯一输入和Enhancer重写稿；正式正文直接使用增强稿，不得再生成第三版正文，也不得改写单集梗概。

阶段二结束时生成`stage-two-acceptance.json`，一次绑定全局故事、拓扑、情绪脊、路线记账与全部梗概。阶段三不得逐集重跑这些全局门禁，只核对该回执与`run-state.json`的绑定；最终闭包再完整核对一次全局依赖哈希。

阶段三按`action_contracts.py`与`run_state.py status`一次只推进当前一集的一个原子动作。编剧、Enhancer、场面复检和普通观众冷读使用动作隔离的子Agent；父子Thread默认文件系统隔离，父任务把标准输入正文和claim返回的SHA-256随task消息发送，子Agent返回绑定该哈希的`nextplay.episode-child-result.v1`。父任务必须用`commit_child_result.py`验证和落盘，不能手工摘取正文。写作与增强串行，两项只读复检可并行。

`run_state.py`为每次转换登记标准输入、owner、有期限租约、输出合同和哈希，并直接返回`next_episode_id/next_actions`。编排失败和内容失败分开计数：租约过期自动回收；同一动作三次编排失败后要求改用父端执行、消息传输或保存`IN_PROGRESS`，不熔断正文；同一内容动作连续失败三次才熔断。任何超时都不是PASS。复检问题要求整集重写时，使用`run_state.py rewrite`归档当前失败尝试并回到Screenwriter；不得困在只允许局部修复的状态，也不得覆盖已验收分集。

每集开始时先生成适配源；Screenwriter只能看连续故事输入及其写作references。Enhancer只能看脚本生成的唯一输入，其中逐字包含当前草稿、停止边界、Enhancer reference和完整中文话茬reference。更早正文、旧审稿记录、无关路线和验收答案不得进入两者的工作区。

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
适配源 → 连续故事材料 → 材料门禁 → Screenwriter草稿与回执 → Enhancer唯一输入 → Enhancer重写稿
→ 增强稿原样成为正式正文 → 确定性结构校验 → 场面复检与独立冷读
→ 必要时合并问题单并由Enhancer局部修复 → 单集验收回执 → 放行
```

Enhancer可以全面重写表达层，包括场面动作组织、全部对白、话轮、停顿和反应，不要求保留草稿原句；禁止改变剧情事实、行动结果、选择、结局和停止边界。场面复检和独立冷读都只判不改；问题按正文行号合并后仍由Enhancer在同一阶段局部修复，未命中内容逐字不变。任何覆盖整集的修改必须重新经过Screenwriter与完整Enhancer，不能借局部修复或验收生成第三版正文。

## 阶段四门禁

每个结构、场面与冷读门禁在当步封存绑定当前输入的回执。单集Acceptance只汇总这些已提交动作的标准路径与SHA-256，不重放任何门禁。阶段四仅核对阶段二验收、全路径首次出场、全部单集Acceptance和运行状态，再调用唯一业务组装器。

完成凭证使用`nextplay.episode-completion.v14`，绑定：

- `run-basis.json`
- `mainline-story-input.json`
- `unnumbered-emotional-movement.json`
- `mainline-story.json`
- `mainline-story-review.json`
- `decision-fissure-audit.json`
- `decision-fissure-review.json`
- `route-duration.json`
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
- 全部适配源、连续故事材料、编剧输入、编剧草稿、编剧回执、Enhancer输入和增强稿
- 全部场面复检回执、独立冷读回执和单集验收回执
- 发生局部修复时的合并问题单、修复输入和修复回执
- 最终业务JSON

任一绑定文件变化，旧完成凭证立即失效。

工程接收层不得把单独九字段JSON、结构校验PASS或生产者声明的完成状态当作正式交付。接收层必须自行运行`verify_deliverable.py`，同时校验当前`episode-business.json`、`completion-receipt.json`和`episode-handoff.json`，且只在退出码为0并输出独立一行`DELIVERABLE_ACCEPTED`时完成投影；否则保持`正在生成中`。

## 修改模式

- 先区分内部返修与用户局部编辑。Agent为修正首次生成结果而改变故事或拓扑时，仍从最早失效阶段重跑；用户已经在现有分集结果上新增、插入、修改、删除或重连节点时，读取`local-node-editing.md`，以用户操作后的当前节点关系为事实源，不重新生成情绪脊或全局拓扑。
- 九字段业务结果的受控局部修改必须提供完整基线缓存，而不是只提供旧业务JSON。工程侧局部编辑由调用方提供目标节点、直接前置、直接后续和相关人物资产即可；工程route只作定位上下文，不进入本节业务缓存合同。
- `--baseline-root`指向修改前缓存。
- 每个允许变化的分集分别传`--allowed-changed episode-xxx`。
- 只改台词时传`--change-scope dialogue`。
- 未授权分集必须逐字不变；局部修改期间`topology.md`必须逐字节不变。
- 局部正文表达或对白修改期间，`story-treatment.json`和全部`episode-synopses/*.json`也必须不变。
- 局部梗概或本集因果修改必须同步维护完整故事对应段落并重跑故事、故事—拓扑和梗概集合门禁；没有用户授权的梗概和正文不得顺带变化。
- 改动正文后必须重新运行对应集的确定性结构验收；用户要求或用户意图合同变化时，所有受其绑定的冻结材料必须重建。
- 非用户局部编辑导致的内部拓扑返修不能使用局部正文模式，必须从阶段二重新执行并重建受影响下游。用户明确执行的局部结构编辑只重建授权节点内容和受影响接缝；工程图的字段写回、稳定节点引用和边更新由调用方适配层负责，不改本Skill九字段业务合同。
