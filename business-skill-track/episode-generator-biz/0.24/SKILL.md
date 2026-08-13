---
name: episode-generator-biz
description: "当大纲生成师已经产出游戏企划，以及资产设计师已经产出角色描述、场景描述和道具描述后，用户要求整理、补全、确认或修改互动影游的分集内容、互动结构、分集剧情、完整剧本、逐集台词、选择、分支、汇合或结局时，使用本 Skill。已有分集结果后，用户只修改某一集的梗概、剧情、台词、人物关系、互动选择、跳转方向或结局时，也使用本 Skill，并保持未指定内容不变。初次生成必须同时具备游戏企划、角色描述、场景描述和道具描述；缺少游戏企划时先使用大纲生成师，缺少角色、场景或道具描述时先使用资产设计师。最终只返回由分集编号、分集标题、分集剧本、剧本分析、关联角色、关联场景、关联道具、是否结局和互动节点组成的分集列表 JSON，不输出内部分析过程。不要用于初始故事构思、资产设计、故事板、分镜、图像提示词、视频提示词或直接生成图片视频；资产图片或资产Prompt使用资产生成师，故事板、分镜或镜头Prompt使用故事版和视频生成师。"
---

# 分集规划师

## 目标

把四项上游输入转成一份通过全部门禁的`分集列表`JSON。先完成全篇故事，再把故事结构化为拓扑和全体分集梗概，最后逐集写成剧本。当前阶段未通过时，不得开始下一阶段，也不得提前返回部分结果。

脚本负责检查合同、结构、证据、指纹和修改边界。Agent负责判断人物、因果、信息吞吐和台词是否真正成立。不得把脚本通过等同于语义质量通过，也不得用主观判断绕过脚本。

## 核心约定

- 最新且明确的用户要求是创作硬约束，优先于上游建议、Skill默认偏好和内部启发式。除安全边界、输出合同或客观不可实现外，不得否定、替换或删除用户指定内容。
- 用户前后要求无法同时成立时，暂停并启动AskUser；用户回答前不得自行选择或继续生成。
- 先建立主干情绪脊，再写完整的互动故事；从故事中已经发生的真实戏剧裂缝识别分支，不得先画空分支树再让故事迁就结构。
- 全部项目共用本 Skill 定义的唯一因果组织与结局拓扑规则；时长只控制场面数量和展开容量，不触发结构规则切换。
- 题材只作为稀疏的场面导演：从已冻结的`genre_tone`提取不超过3项类型承诺，安放到合适情绪窗口；不得创建第二套故事合同、节点义务或逐集打卡表。
- 完整故事、正式拓扑、全体分集梗概和逐集剧本是四层不同材料：故事决定发生什么，拓扑决定如何连接，梗概决定每集承载哪段变化，剧本负责把冻结梗概实际演出。下层不得反向替上层补故事。
- 一个`episode-xxx`对应一集有完整剧情的节点。有效选择只在来源分集的`互动节点`中封装一次。
- 选择后的不同事实先分别演出，取得共同事实后才能带差异汇合；禁止空合流和伪分支。
- 冻结拓扑是剧本锚。未明确解冻前，正文不得修改节点、边、选择、条件、状态效果或结局。
- 写作按相邻因果推进：触发、判断、欲望、行动、阻力、调整、即时后果和下一压力不得跳步。
- 当前运行环境按单 Agent 执行。不得假设、调用或等待尚未配置的子 Agent；用冻结材料、有限工作集和分批换档控制长篇质量，但所有既有阶段、脚本与门禁仍由当前 Agent 完整执行。
- `episode-001`带选择时，必须先完整演出第一集剧情，再显示选择；禁止空剧情直接出选项。
- 默认主动完成全部阶段。只有输入缺失、用户要求冲突或必须取得新授权时才询问用户。

## 对外边界

执行前完整读取`references/external-output-boundary.md`。

- 正式结果只有九字段`分集列表`JSON；不得把其他文件或工程结构作为交付结果。
- 情绪脊、完整故事、拓扑、梗概集合、缓存、复检材料、回执、完成凭证和错误详情都是私有运行材料，不进入正式结果。
- 长任务只允许发送四条面向用户的阶段状态，每条在首次进入对应阶段时最多发送一次：冻结基础、情绪脊和完整故事期间发送`正在生成故事`；投影拓扑和冻结全体梗概期间发送`正在生成分支`；逐集写作与逐集放行期间发送`正在生成剧本`；最终检查与业务组装期间发送`正在最终验收`。不得发送其他过程消息。

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

## 阶段二：完整故事、拓扑与全体梗概

### 读取

- `references/emotional-spine-state-graph.md`
- `references/story-treatment-and-decomposition.md`
- `references/genre-direction.md`
- `references/run-basis-and-stage-gates.md`中的阶段二

### 执行

1. 依据体量、用户硬约束和结局计划确定具体剧情节点数与互动预算；优先落入上游软区间，不为凑数破坏因果。
2. 先生成`emotional-spine.json`，建立全篇PAD/VAD主干；此时不创建正式拓扑。
3. 生成`story-treatment.json`。用连贯自然语言写清共同主线、人物关系、行动—阻力—调整—后果、选择的戏剧原因、各选项的即时结果与持续差异、汇合条件和全部结局回收。它是完整互动故事，不是分集清单，也不是只写主线后补选择。
   - 依据`genre-direction.md`把最多3项类型承诺绑定到故事中已经需要的场面；类型处理只改变场面的动作、反应、台词或效果强度，不为兑现题材新增节点。
4. 对完整故事做一次独立全局冷读并封存`story-treatment-review.json`。故事门禁未通过时，只返修完整故事。
5. 在完整故事内先审计玩家可执行动作及其即时状态差，再依各路线的行动后果与情绪结算决定继续、汇合或结束；不得先指定拓扑形状再补写情绪理由。只把已经成立的事件和选择投影为`topology.md`，明确唯一入口、节点、后继、选择问题、选项、即时结果、汇合和结局；不得在拓扑阶段发明新剧情。重大路线完成独立目标、阻力、状态变化和情绪轨迹后可以带差异汇合，不以是否改变可达结局集合判断其有效性；至少一个正式结局正面兑现核心目标与类型期待，题材存在可信致命风险时包含死亡或同等不可逆失败。
6. 把规范化情绪脊SHA-256写入拓扑机器注释，并校验完整故事、情绪脊和拓扑相互一致。
7. 按冻结拓扑一次生成全部`episode-synopses/<episode-id>.json`。每集梗概必须从完整故事中切出连续的因果变化，写清处境、目标、行动、阻力、调整、结果和下一入口；不得只列事实或风险。
8. 对全体梗概做一次整体拆解复检并封存`synopsis-set-review.json`：确认完整覆盖故事、顺序正确、没有遗漏或重复、分支不串线、汇合有共同事实、结局承接对应路线、各集推进量不过度失衡。

### 门禁

```bash
python3 scripts/validate_emotional_spine.py <缓存目录>/emotional-spine.json
python3 scripts/story_treatment_gate.py packet <缓存目录> --output <临时完整故事复检包.json>
python3 scripts/story_treatment_gate.py seal <缓存目录> <完整故事复检结果.json>
python3 scripts/story_treatment_gate.py verify <缓存目录>
python3 scripts/validate_emotional_topology.py <缓存目录>/topology.md --spine <缓存目录>/emotional-spine.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_topology.py <缓存目录>/topology.md --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_story_topology.py <缓存目录>/story-treatment.json <缓存目录>/topology.md --expected-endings E
python3 scripts/synopsis_set_gate.py packet <缓存目录> --output <临时梗概集合复检包.json>
python3 scripts/synopsis_set_gate.py seal <缓存目录> <梗概集合复检结果.json>
python3 scripts/synopsis_set_gate.py verify <缓存目录>
```

全部命令PASS后，完整故事、拓扑和全体梗概一起冻结，才允许写任何分集正文。PASS至少代表：完整故事可独立复述且分支与结局成立；拓扑编号连续、入口唯一、全部节点可达、无环、无断头、所有节点可达结局、选择目标有效、选择对应情绪拐点、汇合没有清除路线差异、结局数量正确；全体梗概完整覆盖故事且每集形成因果变化。脚本负责合同、指纹、数量、映射和证据完整性；Agent仍须判断每条路线的去向是否由行动后果与情绪结算产生，以及期待性结局、题材相称的失败力度和故事整体是否成立。

命令中的`E`、`F`、`X`分别取自已通过阶段一门禁的结局总数、正式结局数和失败结局数，不得使用模板常量。

## 阶段三：逐集剧本写作与逐集放行

### 读取

- `references/causal-episode-writing.md`
- `references/chinese-dialogue-craft.md`
- `references/dramatization-completion.md`
- `references/character-appearance-validation.md`
- 当前题材标签命中`references/genre-direction.md`中的模块时读取该文件；否定标签不得误触发，未命中时不增加题材义务
- 当前集出现推动剧情的书面信息时，再读取`references/written-text-to-dialogue.md`
- 冷读时只读取脚本生成的复检包；不得提前读取`references/episode-quality-review.md`后自行宣布通过

### 单 Agent 工作集

阶段三开始时，按冻结拓扑把相邻因果节点划成不超过3集的工作批次。共同主线、不同分支、汇合段和结局段分别成批；不得把互斥路线正文放进同一活跃工作集。批次只限制当前需要关注的材料，不是生成或验收单位，也不改变拓扑、编号、节点数和正式输出。工作集范围属于Agent执行约束；脚本无法检查模型实际关注了哪些上下文，但仍强制检查正文不得抢跑、前置回执有效和每集独立放行。

- 同一时刻只写当前一集。不得先生成整批正文，再回头补验收。
- 当前集活跃材料只包括：冻结梗概、当前节点、已放行直接前置的真实结尾、仍有效状态差异、相关人物与资产、世界规则和直接后续入口。
- 已放行的更早正文保留在缓存中作为证据，但退出活跃工作集；除定位连续性问题外，不得重新通读或复制进当前写作上下文。
- 每完成一批，先确认批内各集`verify-one`仍为PASS，再切换到下一批；切换后不再把草稿、旧审稿意见、淘汰方案和无关路线材料纳入活跃工作集，只从冻结材料重建下一批工作集。缓存证据不得删除或改写。
- 批次中的每一集都使用同一门禁。正文低于对应节点职能的软篇幅且缺少行动、阻力、调整或可见后果，或者出现事实罗列、条件式代写、人物口吻无法区分、用解释代替场面，均视为当前集未通过；只返修当前集，不能以“后续统一润色”放行。

### 每集循环

按上述批次顺序执行，批次内仍按冻结拓扑的拓扑序一次只处理一集；当前集的全部直接前置分集必须已经通过：

1. 只携带已冻结的当前集梗概、当前节点、直接前置结果、仍有效的状态差异、相关人物与资产、世界规则和直接后续入口。完整故事只允许检索与当前梗概直接对应的逐字来源，不得重新载入全文或借它越过当前梗概塞入后续事件。
2. 先建立`dramatization-plans/<episode-id>.json`：把冻结梗概视为事件，先写不可从正文倒填的`Process Chain`。每个过程写明冻结场景、执行者、触发依据、动作对象、阻力或核验、现场结果；较长事件至少四个过程。执行者或关键对象不在资产中时，停止并退回上游，不准用旁白让机构自动完成结果。运行`dramatization_gate.py plan`，PASS前不得写正文。
3. 把冻结梗概原样写入`episodes/<episode-id>.md`，再依据已通过的场面展开计划完成九字段正文。不得临时改写梗概、拓扑或选择，也不得把梗概原句当成正文粘贴。
4. 单独提取台词，执行轻量台词复写并放回原位。
5. 首次出场角色出现时，立即把身份、关系、当前必要性三条逐字证据写入`character-introductions.json`。
6. 运行当前集结构门禁。
7. 结构门禁PASS后生成场面展开复检包。每个过程分别引用行动、阻力或核验、结果三处按序且不重复的正文证据；事件结束状态晚于全部过程。任何重大结果没有过程链，或过程只能靠一句旁白证明，均视为未展开。场面展开回执PASS前不得进入独立冷读。
8. 场面展开PASS后再换档到独立冷读。冷读只允许引用脚本生成的当前集质量复检包和独立复检reference，不得读取场面展开计划、写作笔记、作者计划、预期答案或后续剧情，随后验证理解门、梗概与正文一致及其余质量项。
9. 有问题时只返修当前集正文；若发现冻结梗概本身无法成立，停止阶段三并退回阶段二，重建受影响梗概集合及其回执，不能在正文中暗改梗概。
10. 正文变化后，场面展开回执与冷读回执同时失效，必须依次重建。两类回执都PASS且当前集`verify-one` PASS，才开始下一集正文。

### 当前集门禁

```bash
python3 scripts/dramatization_gate.py plan <缓存目录> <分集编号>
python3 scripts/validate_episode.py <缓存目录> <分集编号>
python3 scripts/dramatization_gate.py packet <缓存目录> <分集编号> --output <临时场面展开复检包.json>
python3 scripts/dramatization_gate.py seal <缓存目录> <分集编号> <场面展开复检结果.json>
python3 scripts/dramatization_gate.py verify-one <缓存目录> <分集编号>
python3 scripts/episode_quality_gate.py packet <缓存目录> <分集编号> --output <临时复检包.json>
python3 scripts/episode_quality_gate.py seal <缓存目录> <分集编号> <复检结果.json>
python3 scripts/episode_quality_gate.py verify-one <缓存目录> <分集编号>
```

每集通过必须同时满足：全体梗概集合已有当前有效回执；事件过程链完整覆盖梗概并绑定完整故事；过程执行者、场景和对象可由冻结资产执行；九字段结构、拓扑和资产一致；每个过程都有按序且不重复的行动、阻力核验和结果证据；理解门四项有互不替代的正文证据；全部冷读项覆盖；问题为空；当前正文、reference、冻结梗概集合和用户意图指纹与回执一致。

写完全部分集后运行：

```bash
python3 scripts/dramatization_gate.py verify <缓存目录>
python3 scripts/episode_quality_gate.py verify <缓存目录>
```

全体回执PASS才进入阶段四。

## 正文规则

- 单集梗概只能概括本集完整剧本实际演出的事件，不能把未演出的前史、未来结果、作者解释或其他分集内容当成本集剧情；梗概必须用自然语言独立读懂。
- 单集梗概在阶段二已经整体冻结。阶段三只能把它演成正文，不能为方便写作把梗概缩短成事实清单、换成另一段剧情或把多集事件挤进当前集。
- 场次使用`【场景名称·时段·内/外】`。
- 叙述按正常段落书写，不使用`△`、`出场：`、镜号、景别、机位、运镜或审稿标签。
- 对白使用`人物：台词`，不使用台词引号。
- 选择必须是玩家可执行的动作，并指向冻结拓扑中的真实目标集。
- 每集只解决当前主要问题并形成下一压力；不要一次塞入多轮设定、身份和反转。
- 不得用“若走某路线”“另一种情况下”“两种来路”“视玩家此前选择”等条件式文字同时代写互斥路线；当前集只演出其冻结前置实际带来的这一条事实。汇合节点必须先取得拓扑规定的共同事实，再在共同处境中继续。
- 人物、组织、装置、能力和关键名词首次影响剧情时，当场说明其身份、关系和必要性。

## 阶段四：最终检查与业务组装

阶段四不再创作、复写或改变拓扑，只检查全部冻结结果并组装正式JSON。

### 最终门禁

```bash
python3 scripts/validate_user_intent_lock.py project <缓存目录>
python3 scripts/story_treatment_gate.py verify <缓存目录>
python3 scripts/validate_story_topology.py <缓存目录>/story-treatment.json <缓存目录>/topology.md --expected-endings E
python3 scripts/synopsis_set_gate.py verify <缓存目录>
python3 scripts/validate_character_appearances.py <缓存目录> --asset-catalog <缓存目录>/asset-catalog.json --introductions <缓存目录>/character-introductions.json
python3 scripts/dramatization_gate.py verify <缓存目录>
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
- 改完整故事中的事件、节点、边、条件、选择或结局：解冻阶段二，从最早受影响材料重新执行，使受影响正文和全部下游回执失效。
- 只改某集梗概或本集因果且拓扑不变：同步修改完整故事对应段落和授权梗概，重新通过完整故事、故事—拓扑及梗概集合门禁；未授权梗概与正文保持不变，再重写受影响正文。
- 只改某集正文表达或对白且冻结梗概不变：以修改前缓存作为`--baseline-root`，逐个用`--allowed-changed <episode-id>`授权；未授权分集必须逐字不变，完整故事、拓扑和梗概集合必须不变。
- 只改对白：增加`--change-scope dialogue`；授权分集内的非台词内容、事实、动作、状态、选择和结尾也不得变化。
- 创建、修改、重做和恢复都返回当前完整结果，不只返回变化片段。

详细参数和失效范围读取`references/run-basis-and-stage-gates.md`中的修改模式。不得因为局部修改而跳过受影响分集的台词复写、冷读和回执重建。

## 完成条件

以下条件全部成立才算完成：

- 阶段一和阶段二门禁全部PASS，拓扑已冻结。
- 完整互动故事已通过全局冷读；正式拓扑只能投影该故事中已经成立的选择和结局。
- 全体分集梗概已完整覆盖故事并整体冻结，不存在遗漏、重复、串线或明显失衡。
- 每集都独立完成写作、台词复写、冷读、返修和当前回执封存。
- 每集在写作前都有通过门禁的场面展开计划，正文完成后每个关键拍都有逐字演出证据和真实状态变化；该计划只用于完成度审计，不进入独立冷读或正式结果。
- 所有梗概都先于任何完整剧本通过集合门禁，且不存在正文反向改写冻结梗概。
- 用户意图、全路径首次出场和全体逐集回执全部PASS。
- 正式JSON严格符合九字段合同，分集数等于冻结拓扑节点数。
- 第一项是具有非空完整剧本的`episode-001`。
- 每个有效选择只在来源分集`互动节点`中出现一次。
- 组装后的业务JSON再次通过独立业务校验。
- 最终对外只返回完整业务JSON，不包含内部过程或其他工程结构。
