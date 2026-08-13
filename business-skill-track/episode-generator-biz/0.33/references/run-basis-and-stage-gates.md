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
→ mainline-story.json + mainline-story-review.json
→ decision-fissure-audit.json + decision-fissure-review.json
→ story-treatment.json + story-treatment-review.json
→ topology.md
→ route-duration.json
→ emotional-spine.json
→ episode-synopses/*.json + synopsis-set-review.json
```

情绪脊合同与拓扑格式分别以`emotional-spine-state-graph.md`和`validate_topology.py`为准；完整故事与全体梗概合同以`story-treatment-and-decomposition.md`为准。

依次运行：

```bash
python3 scripts/build_stage_two_input.py CACHE_ROOT --output CACHE_ROOT/stage-two-input.json
python3 scripts/validate_emotional_movement.py CACHE_ROOT/unnumbered-emotional-movement.json --stage-two-input CACHE_ROOT/stage-two-input.json
python3 scripts/mainline_story_gate.py packet CACHE_ROOT --output MAINLINE_PACKET.json
python3 scripts/mainline_story_gate.py seal CACHE_ROOT MAINLINE_REVIEW.json
python3 scripts/mainline_story_gate.py verify CACHE_ROOT
python3 scripts/decision_fissure_gate.py packet CACHE_ROOT --output FISSURE_PACKET.json
python3 scripts/decision_fissure_gate.py seal CACHE_ROOT FISSURE_REVIEW.json
python3 scripts/decision_fissure_gate.py verify CACHE_ROOT
python3 scripts/story_treatment_gate.py packet CACHE_ROOT --output TREATMENT_PACKET.json
python3 scripts/story_treatment_gate.py seal CACHE_ROOT TREATMENT_REVIEW.json
python3 scripts/story_treatment_gate.py verify CACHE_ROOT
python3 scripts/validate_topology.py CACHE_ROOT/topology.md --movement CACHE_ROOT/unnumbered-emotional-movement.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_story_topology.py CACHE_ROOT/story-treatment.json CACHE_ROOT/topology.md --expected-endings E
python3 scripts/validate_route_duration.py CACHE_ROOT/route-duration.json CACHE_ROOT/topology.md CACHE_ROOT/stage-two-input.json
python3 scripts/validate_emotional_spine.py CACHE_ROOT/emotional-spine.json
python3 scripts/validate_emotional_topology.py CACHE_ROOT/topology.md --spine CACHE_ROOT/emotional-spine.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/synopsis_set_gate.py packet CACHE_ROOT --output SYNOPSIS_SET_PACKET.json
python3 scripts/synopsis_set_gate.py seal CACHE_ROOT SYNOPSIS_SET_REVIEW.json
python3 scripts/synopsis_set_gate.py verify CACHE_ROOT
```

必须严格按以上顺序执行。情绪运动通过后先写并冻结无分支语言的线性主线；主线通过前不得生长支线，支线故事图通过前不得编号拓扑。拓扑后必须枚举全部路线分钟数，所有路线低于上游上限后才生成逐节点情绪脊与梗概。Agent还必须判断：主线是否完整；每个选项即时后果后是否先做结束判断；提前结局是否因果充分；未结束路线是否继续扫描裂缝；主线路径是否可辨认但不限制其他路线长度；所有结局路径是否至少2个有完整剧情的节点。语义不成立时，即使脚本PASS也不得放行。

## 阶段三门禁

全体`episode-synopses/<episode-id>.json`已在阶段二一次生成并由`synopsis-set-review.json`整体冻结。阶段三为当前集建立适配源、连续故事材料、写作输入、Screenwriter草稿、Enhancer增强稿及写后回执；正式正文直接使用增强稿，不得再生成第三版正文，也不得生成、缩写或改写单集梗概。全部中间材料都是私有文件，不增加正式业务字段。

阶段三先按冻结拓扑划分工作批次，每批最多3个相邻因果节点；共同主线、互斥分支、汇合段和结局段不得混成一个活跃工作集。编剧与Enhancer优先使用彼此隔离的工作区；批内执行“一集写作、一集增强、一集确定性结构验收、一集放行”。

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
→ 增强稿原样成为正式正文 → 确定性结构校验 → 放行
```

取消增强稿后的过程检查与普通观众冷读。不得生成场面展开计划、过程复检包、质量复检包或相关回执；也不得以验收名义重写、润色、缩写Enhancer增强稿。结构校验只检查合同字段、拓扑关系、资产白名单、停止边界和增强稿逐字一致性。

## 阶段四门禁

阶段四先验证全局用户意图、全路径首次出场和所有当前回执，再调用唯一业务组装器。组装器从冻结拓扑和逐集正文确定性映射九字段JSON，并再次执行全部项目门禁。

完成凭证使用`nextplay.episode-completion.v8`，绑定：

- `run-basis.json`
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
- 全部适配源、连续故事材料、编剧输入和编剧草稿
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
- 改动正文后必须重新运行对应集的确定性结构验收；用户要求或用户意图合同变化时，所有受其绑定的冻结材料必须重建。
- 非用户局部编辑导致的内部拓扑返修不能使用局部正文模式，必须从阶段二重新执行并重建受影响下游。用户明确执行的局部结构编辑只重建授权节点内容和受影响接缝；工程图的字段写回、稳定节点引用和边更新由调用方适配层负责，不改本Skill九字段业务合同。
