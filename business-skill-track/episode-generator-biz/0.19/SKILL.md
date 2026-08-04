---
name: episode-generator-biz
description: "当大纲生成师已经产出游戏企划，以及资产设计师已经产出角色描述、场景描述和道具描述后，用户要求整理、补全、确认或修改互动影游的分集内容、互动结构、分集剧情、完整剧本、逐集台词、选择、分支、汇合或结局时，使用本 Skill。已有分集结果后，用户只修改某一集的梗概、剧情、台词、人物关系、互动选择、跳转方向或结局时，也使用本 Skill，并保持未指定内容不变。初次生成必须同时具备游戏企划、角色描述、场景描述和道具描述；缺少游戏企划时先使用大纲生成师，缺少角色、场景或道具描述时先使用资产设计师。最终只返回由分集编号、分集标题、分集剧本、剧本分析、关联角色、关联场景、关联道具、是否结局和互动节点组成的分集列表 JSON，不输出内部分析过程。不要用于初始故事构思、资产设计、故事板、分镜、图像提示词、视频提示词或直接生成图片视频；资产图片或资产Prompt使用资产生成师，故事板、分镜或镜头Prompt使用故事版和视频生成师。"
---

# 分集规划师

## 目标

把四项上游输入转成一份通过全部门禁的`分集列表`JSON。按阶段执行；当前阶段未通过时，不得开始下一阶段，也不得提前返回部分结果。

脚本负责检查合同、结构、证据、指纹和修改边界。Agent负责判断人物、因果、信息吞吐和台词是否真正成立。不得把脚本通过等同于语义质量通过，也不得用主观判断绕过脚本。

## 核心约定

- 最新且明确的用户要求是创作硬约束，优先于上游建议、Skill默认偏好和内部启发式。除安全边界、输出合同或客观不可实现外，不得否定、替换或删除用户指定内容。
- 用户前后要求无法同时成立时，暂停并启动AskUser；用户回答前不得自行选择或继续生成。
- 先建立主干情绪脊，再从真实戏剧裂缝识别分支；不得先画分支树再让故事迁就结构。
- 一个`episode-xxx`对应一集有完整剧情的节点。有效选择只在来源分集的`互动节点`中封装一次。
- 选择后的不同事实先分别演出，取得共同事实后才能带差异汇合；禁止空合流和伪分支。
- 冻结拓扑是剧本锚。未明确解冻前，正文不得修改节点、边、选择、条件、状态效果或结局。
- 写作按相邻因果推进：触发、判断、欲望、行动、阻力、调整、即时后果和下一压力不得跳步。
- `episode-001`带选择时，必须先完整演出第一集剧情，再显示选择；禁止空剧情直接出选项。
- 默认主动完成全部阶段。只有输入缺失、用户要求冲突或必须取得新授权时才询问用户。

## 对外边界

执行前完整读取`references/external-output-boundary.md`。

- 正式结果只有九字段`分集列表`JSON；不得把其他文件或工程结构作为交付结果。
- 情绪脊、拓扑、缓存、复检材料、回执、完成凭证和错误详情都是私有运行材料，不进入正式结果。
- 默认不发送过程消息。平台强制显示长任务状态时，只发送`正在生成中`。

## 输入与输出

进入阶段一前完整读取：

1. `references/business-interface.md`
2. `references/episode-output-schema.md`
3. `references/upstream-input-translation.md`

初次生成必须读取`游戏企划`、`角色描述`、`场景描述`、`道具描述`。缺少哪一项，只追问哪一项。`剧情节点总数建议`是软区间；缺失不阻塞。只有用户明确要求固定为N集时，节点数才是硬约束。

正式输出顶层只有`分集列表`。每集严格使用以下九个一级字段，顺序固定：

1. `分集编号`
2. `分集标题`
3. `分集剧本`
4. `剧本分析`
5. `关联角色`
6. `关联场景`
7. `关联道具`
8. `是否结局`
9. `互动节点`

字段层级、类型、子字段和一致性规则以`references/business-interface.md`为唯一接口合同。

## 阶段放行规则

每个阶段都按同一顺序执行：

1. 读取本阶段指定reference。
2. 生成本阶段私有材料。
3. 运行本阶段列出的全部命令。
4. 检查命令退出码和输出；只有全部显示`PASS`才进入下一阶段。
5. 任一命令失败时，只返修最早失败阶段及其受影响下游，然后完整重跑该阶段门禁。

不得省略命令、手写PASS、复制旧回执、以“已经检查过”代替脚本，或在门禁未通过时继续。

## 阶段一：冻结运行基础

### 读取

- `references/user-intent-lock.md`
- `references/run-basis-and-stage-gates.md`中的阶段一

### 执行

1. 把本轮用户要求原文保存为`user-request.md`，建立`user-intent-lock.json`。
2. 按上游输入冻结`run-basis.json`：故事核心、主题、题材基调、世界规则、体量、结局计划、必保事件和角色运行边界。
3. 建立`asset-catalog.json`，只登记正式角色、场景、道具及允许的角色别名。
4. 初始化`character-introductions.json`，供阶段三登记全路径首次出场证据。

四项输入是否齐全必须在创建冻结材料前判断；脚本负责检查冻结材料是否完整和自洽，不能证明Agent没有虚构缺失的上游事实。

### 门禁

```bash
python3 scripts/validate_user_intent_lock.py contract <缓存目录>
python3 scripts/validate_run_basis.py <缓存目录>
```

两个命令都PASS才冻结阶段一。`needs-user`、四项输入缺失、资产名非法或重名、结局数量矛盾、角色运行边界缺失时不得进入阶段二。

## 阶段二：情绪脊与分支拓扑

### 读取

- `references/emotional-spine-state-graph.md`
- `references/run-basis-and-stage-gates.md`中的阶段二

### 执行

1. 依据体量、用户硬约束和结局计划确定具体分集节点数与互动预算；优先落入上游软区间，不为凑数破坏因果。
2. 先生成`emotional-spine.json`，建立全篇PAD/VAD主干，不创建分支。
3. 只在真实价值分歧与情绪拐点同时存在时创建选择。
4. 生成`topology.md`，明确唯一入口、节点、后继、选择问题、选项、选择结果、汇合和结局。
5. 把规范化情绪脊SHA-256写入拓扑机器注释，绑定两份材料。

### 门禁

```bash
python3 scripts/validate_emotional_topology.py <缓存目录>/topology.md --spine <缓存目录>/emotional-spine.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_topology.py <缓存目录>/topology.md --expected-endings E --expected-formal F --expected-failure X
```

两个命令都PASS才冻结拓扑。未通过时不得写任何分集正文。PASS至少代表：编号连续、入口唯一、全部节点可达、无环、无断头、所有节点可达结局、选择目标有效、选择对应情绪拐点、结局数量正确。语义上还必须确认每个选择有代价、即时差异和后续承接；脚本不能替代这项判断。

命令中的`E`、`F`、`X`分别取自已通过阶段一门禁的结局总数、正式结局数和失败结局数，不得使用模板常量。

## 阶段三：逐集写作与逐集放行

### 读取

- `references/causal-episode-writing.md`
- `references/chinese-dialogue-craft.md`
- `references/character-appearance-validation.md`
- 当前集出现推动剧情的书面信息时，再读取`references/written-text-to-dialogue.md`
- 冷读时只读取脚本生成的复检包；不得提前读取`references/episode-quality-review.md`后自行宣布通过

### 每集循环

按冻结拓扑的拓扑序一次只处理一集；当前集的全部直接前置分集必须已经通过：

1. 只携带当前节点、直接前置结果、仍有效的状态差异、相关人物与资产、世界规则和直接后续入口。
2. 先写当前集私有梗概草案到`episode-synopses/<episode-id>.json`。梗概必须用自然语言独立说清人物面对的问题、本集实际变化和下一入口。
3. 生成梗概理解包，独立冷读；三项无法只凭梗概复述时，只返修梗概，不得写完整剧本。
4. 梗概理解回执PASS后，才把同一梗概写入`episodes/<episode-id>.md`并完成九字段正文。
5. 单独提取台词，执行轻量台词复写并放回原位。
6. 首次出场角色出现时，立即把身份、关系、当前必要性三条逐字证据写入`character-introductions.json`。
7. 运行当前集结构门禁。
8. 生成当前集完整冷读包，验证理解门、梗概与正文一致及其余质量项。
9. 有问题时只返修当前集；正文变化后重新生成冷读包。问题清空后封存回执。
10. 当前集`verify-one` PASS后，才创建下一集梗概。禁止先批量写正文或梗概，再补回执。

### 当前集门禁

```bash
python3 scripts/episode_quality_gate.py synopsis-packet <缓存目录> <分集编号> --output <临时梗概复检包.json>
python3 scripts/episode_quality_gate.py synopsis-seal <缓存目录> <分集编号> <梗概复检结果.json>
python3 scripts/episode_quality_gate.py synopsis-verify-one <缓存目录> <分集编号>
python3 scripts/validate_episode.py <缓存目录> <分集编号>
python3 scripts/episode_quality_gate.py packet <缓存目录> <分集编号> --output <临时复检包.json>
python3 scripts/episode_quality_gate.py seal <缓存目录> <分集编号> <复检结果.json>
python3 scripts/episode_quality_gate.py verify-one <缓存目录> <分集编号>
```

每集通过必须同时满足：梗概可独立读懂且已先行封存；九字段结构正确；前后节点、选择、结局和资产与冻结材料一致；正文非空且场次格式正确；梗概只概括本集正文实际演出的事件；理解门四项有正文证据；全部冷读项覆盖；问题为空；所有证据逐字存在于对应梗概或正文；当前正文、reference和用户意图指纹与回执一致。

写完全部分集后运行：

```bash
python3 scripts/episode_quality_gate.py verify <缓存目录>
```

全体回执PASS才进入阶段四。

## 正文规则

- 单集梗概只能概括本集完整剧本实际演出的事件，不能把未演出的前史、未来结果、作者解释或其他分集内容当成本集剧情；梗概必须用自然语言独立读懂。
- 场次使用`【场景名称·时段·内/外】`。
- 叙述按正常段落书写，不使用`△`、`出场：`、镜号、景别、机位、运镜或审稿标签。
- 对白使用`人物：台词`，不使用台词引号。
- 选择必须是玩家可执行的动作，并指向冻结拓扑中的真实目标集。
- 每集只解决当前主要问题并形成下一压力；不要一次塞入多轮设定、身份和反转。
- 人物、组织、装置、能力和关键名词首次影响剧情时，当场说明其身份、关系和必要性。

## 阶段四：最终检查与业务组装

阶段四不再创作、复写或改变拓扑，只检查全部冻结结果并组装正式JSON。

### 最终门禁

```bash
python3 scripts/validate_user_intent_lock.py project <缓存目录>
python3 scripts/validate_character_appearances.py <缓存目录> --asset-catalog <缓存目录>/asset-catalog.json --introductions <缓存目录>/character-introductions.json
python3 scripts/episode_quality_gate.py verify <缓存目录>
```

全部PASS后，只能用业务组装器生成结果：

```bash
python3 scripts/assemble_business_output.py <缓存目录> <输出目录>/episode-business.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_business_output.py <输出目录>/episode-business.json --asset-catalog <缓存目录>/asset-catalog.json --expected-endings E --expected-formal F --expected-failure X
```

组装器只能映射已验证内容，不得新增、改写或摘要剧本。组装器写入后生成私有完成凭证；业务JSON或任一绑定依赖变化时，凭证立即失效。最终验证PASS后，一次性返回完整`分集列表`JSON；不得返回局部节点或内部材料。

## 修改已有结果

- 改上游事实：重新执行阶段一，并使受影响的阶段二、三、四失效。
- 改节点、边、条件、选择或结局：解冻阶段二，使受影响正文和全部下游回执失效。
- 只改某集因果或对白：以修改前缓存作为`--baseline-root`，逐个用`--allowed-changed <episode-id>`授权；未授权分集必须逐字不变，拓扑必须逐字节不变。
- 只改对白：增加`--change-scope dialogue`；授权分集内的非台词内容、事实、动作、状态、选择和结尾也不得变化。
- 创建、修改、重做和恢复都返回当前完整结果，不只返回变化片段。

详细参数和失效范围读取`references/run-basis-and-stage-gates.md`中的修改模式。不得因为局部修改而跳过受影响分集的台词复写、冷读和回执重建。

## 完成条件

以下条件全部成立才算完成：

- 阶段一和阶段二门禁全部PASS，拓扑已冻结。
- 每集都独立完成写作、台词复写、冷读、返修和当前回执封存。
- 每集梗概都先于完整剧本通过独立理解门，且不存在抢跑梗概或正文。
- 用户意图、全路径首次出场和全体逐集回执全部PASS。
- 正式JSON严格符合九字段合同，分集数等于冻结拓扑节点数。
- 第一项是具有非空完整剧本的`episode-001`。
- 每个有效选择只在来源分集`互动节点`中出现一次。
- 组装后的业务JSON再次通过独立业务校验。
- 最终对外只返回完整业务JSON，不包含内部过程或其他工程结构。
