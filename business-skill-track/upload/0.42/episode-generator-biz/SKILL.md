---
name: episode-generator-biz
description: "当大纲生成师已经产出游戏企划，以及资产设计师已经产出角色描述、场景描述和道具描述后，用户要求整理、补全、确认或修改互动影游的分集内容、互动结构、分集剧情、完整剧本、逐集台词、选择、分支、汇合或结局时，使用本 Skill。已有分集结果后，用户新增、插入、修改、重做或删除某一剧情节点，修改人物关系、互动选择、跳转方向或结局时，也使用本 Skill，并保持未指定内容不变。初次生成必须同时具备游戏企划、角色描述、场景描述和道具描述；缺少游戏企划时先使用大纲生成师，缺少角色、场景或道具描述时先使用资产设计师。正式业务结果只返回由分集编号、分集标题、分集剧本、剧本分析、关联角色、关联场景、关联道具、是否结局和互动节点组成的分集列表 JSON，不输出内部分析过程。不要用于初始故事构思、资产设计、故事板、分镜、图像提示词、视频提示词或直接生成图片视频；资产图片或资产Prompt使用资产生成师，故事板、分镜或镜头Prompt使用故事版和视频生成师。"
---

# 分集规划师

## 目标

把四项上游输入转成一份通过全部门禁的`分集列表`JSON。先完成全篇故事，再把故事结构化为拓扑和全体分集梗概，最后逐集写成剧本。当前阶段未通过时，不得开始下一阶段，也不得提前返回部分结果。

脚本负责检查合同、结构、证据、指纹和修改边界。Agent负责判断人物、因果、信息吞吐和台词是否真正成立。不得把脚本通过等同于语义质量通过，也不得用主观判断绕过脚本。

## 核心约定

- 最新且明确的用户要求是创作硬约束，优先于上游建议、Skill默认偏好和内部启发式。除安全边界、输出合同或客观不可实现外，不得否定、替换或删除用户指定内容。
- 用户前后要求无法同时成立时，暂停并启动AskUser；用户回答前不得自行选择或继续生成。
- 初次生成与用户局部编辑是两个模式。只有初次生成从情绪运动推导路线与节点；已有分集结果上的新增、修改、删除和重连以用户操作后的当前节点关系为事实源，只处理授权节点及其相邻内容，不用情绪脊否定、重构或优化用户改动。
- 先建立不带分集编号的主干情绪运动，再写完整互动故事与路线级拓扑；从故事中已经发生的真实戏剧裂缝识别分支。内部把“单条完整游玩路径需要的展开量”与“全图实际节点数”分开：前者用于防止分支挤短主线，后者只能在全部路线展开后统计。不得把路径体量误当全图节点上限，也不得先按节点预算画空分支树。
- 全部项目共用本 Skill 定义的唯一因果组织与结局拓扑规则；时长只控制场面数量和展开容量，不触发结构规则切换。
- 题材只作为稀疏的场面导演：从已冻结的`genre_tone`提取不超过3项类型承诺，安放到合适情绪窗口；不得创建第二套故事合同、节点义务或逐集打卡表。
- 完整故事、正式拓扑、全体分集梗概和逐集剧本是四层不同材料：故事决定发生什么，拓扑决定如何连接，梗概决定每集承载哪段变化，剧本负责把冻结梗概实际演出。下层不得反向替上层补故事。
- 一个`episode-xxx`对应一集有完整剧情的节点。有效选择只在来源分集的`互动节点`中封装一次。
- 选择后的不同事实先分别演出，取得共同事实后才能带差异汇合；禁止空合流和伪分支。
- 初次生成中，冻结拓扑是剧本锚，未明确解冻前正文不得修改节点、边、选择、条件、状态效果或结局；用户局部编辑模式以其操作后的当前图取代旧锚，只改授权范围。
- 写作按相邻因果推进：触发、判断、欲望、行动、阻力、调整、即时后果和下一压力不得跳步。
- 阶段一、二与最终组装由当前任务执行。阶段三写作若提供隔离子任务能力，只把已经通过材料门禁的连续故事输入交给独立编剧；不得把过程链、验收答案、旧稿问题或未来剧情一同传入。没有隔离能力时按相同文件边界顺序换档，不降低任何门禁。
- `episode-001`带选择时，必须先完整演出第一集剧情，再显示选择；禁止空剧情直接出选项。
- 默认主动完成全部阶段。只有输入缺失、用户要求冲突或必须取得新授权时才询问用户。

## 运行模式

- **初次生成**：按阶段一至四执行，使用情绪运动、完整故事和因果展开生成正式拓扑。
- **用户局部编辑**：执行前完整读取`references/local-node-editing.md`。工程字段或route边只用于识别目标、直接前置和直接后续；节点引用视为不透明标识，不猜测其命名含义。当前工作边界是一集，用户指定情节是硬事实；不读取情绪脊、全局拓扑理由或未来结局来改写用户要求。
- 局部改动能在当前集内接通时直接完成。只有关键人物生死、身份、关系、世界规则、选择去向或下一集成立条件迫使未授权相邻集一起变化时，才用AskUser确认是否扩大修改范围；询问的是相邻修改权限，不是是否接受用户情节。

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

初次生成必须读取`游戏企划`、`角色描述`、`场景描述`、`道具描述`。缺少哪一项，只追问哪一项。`剧情节点总数建议`只在阶段一记录来源，不进入阶段二生成上下文，也不参与路线级拓扑或节点展开；只有用户明确要求固定为N集时，节点数才作为用户硬约束进入阶段二。

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
2. 按上游输入冻结`run-basis.json`：故事核心、主题、题材基调、世界规则、体量、结局计划、必保事件，以及每名角色的身份、明确关系和运行边界。
3. 建立`asset-catalog.json`，只登记正式角色、场景、道具及允许的角色别名。
4. 初始化`character-introductions.json`，供阶段三登记全路径首次出场证据。

四项输入是否齐全必须在创建冻结材料前判断；脚本负责检查冻结材料是否完整和自洽，不能证明Agent没有虚构缺失的上游事实。

### 门禁

```bash
python3 scripts/validate_user_intent_lock.py contract <缓存目录>
python3 scripts/validate_run_basis.py <缓存目录>
```

两个命令都PASS才冻结阶段一。随后运行`build_stage_two_input.py`生成不含上游节点建议的临时阶段二输入包；阶段二不得直接重读`run-basis.json`、`user-request.md`或原始上游输入。`needs-user`、四项输入缺失、资产名非法或重名、结局数量矛盾、角色运行边界缺失时不得进入阶段二。

## 阶段二：完整故事、拓扑与全体梗概

### 读取

- `references/emotional-spine-state-graph.md`
- `references/story-treatment-and-decomposition.md`
- `references/genre-direction.md`
- `references/run-basis-and-stage-gates.md`中的阶段二

### 执行

1. 只读取`stage-two-input.json`和本阶段references，先建立`unnumbered-emotional-movement.json`：不带分集编号、全图节点数量和拓扑形状，锁定压力、反差、释放、控制权变化、观众已知风险与候选戏剧裂缝；同时固定所有结局路径的合法下限为2个剧情节点、上游单次游戏分钟上限和全图互动探索区间。不得预设正式路线节点数。
   - 本次生成必须从该未编号情绪运动重新推导路线；旧`topology.md`、旧`emotional-spine.json`、旧分集梗概、旧分集正文和任何缓存中的节点、边、标题都不是阶段二输入，不得参考、复刻或局部改写。
2. 生成并冻结`mainline-story.json`。它必须是从开场到期待性正式结局的一篇无分支、无条件可能性语言的完整可读故事；不得出现“如果、或者、另一条路线、玩家可以、选择A/B”等表述。主线完整承载核心目标、主要人物变化、关键真相、全部必保事件与期待性类型兑现。运行独立主线冷读并封存`mainline-story-review.json`；未通过前不得生成支线。
3. 完整读取`references/mainline-first-topology.md`，先把冻结主线按原文连续切成`mainline-decomposition.json`。此时只有一条纯直线路径，不得出现支线内容。每个切片是一个候选主线分集，`source_text`必须按顺序、无遗漏、无改写覆盖完整可读故事。运行`validate_mainline_projection.py --decomposition-only`；未PASS不得扫描裂缝。
4. 在任何支线故事或正式拓扑之前生成`decision-fissure-audit.json`。逐字冻结原始`core_goal`并沿纯直线主线节点扫描全部真实决定裂缝；明确交易必须同时审计真实服从与拒绝。裂缝落在切片内部时，只允许把该切片在原文决定边界处继续细分，并重跑主线分解门禁：来源节点停在选择尚未执行处，冻结主线原本执行的动作必须成为一个选项，并从下一主线切片开头继续。原始目标不再继续时`route_ended`必须为真，并标记`ending_scope`。
5. 只读取冻结主线、已通过的主线分解、裂缝审计、未编号情绪运动和阶段二输入，生成`story-treatment.json`。该文件只登记非主线选项生长出的支线事实、选择后果、汇合与全部结局；不得重新概括、改写或重新分配主线。`endings`只含上游预算内的主要结局；`minor_endings`逐一承接所有`ending_scope=minor`动作，动态增加且不占主要结局数量。
   - 依据`genre-direction.md`把最多3项类型承诺绑定到本来需要的场面；不得为类型兑现另造无关主线。
4. 对主线加全部支线做独立全局冷读并封存`story-treatment-review.json`。`interaction_min/max`约束全图选择节点总数，不要求每条路线都经历该次数；提前结局可只经历造成它的选择。每个选项演出即时后果后，先判断该路线是否已经构成因果充分的结局；已结束路线不再承担主线尚未发生的必保事件。只有尚未结算的路线才允许继续、再次选择或带差异汇合。
6. 只把非主线支线展开为新的可演戏剧单位；主线单位及其顺序已经由`mainline-decomposition.json`冻结，不得因支线、结局预算或互动数量重新压缩。支线走多远由各自节点的因果与情绪运动决定。
7. 强制生成两版完整拓扑。先独立完成、编号并保存第一版为`topology-draft-1.md`，然后必定丢弃它：不得从它生成时长、情绪脊、梗概或正文。重新只从冻结主线、主线分解、裂缝审计、支线故事和未编号情绪运动生成第二版。第二版图形结构必须与第一版不同；仅改标题、文字、节点编号或选项名不算不同。若仍相同，丢弃当前第二版并重新生成。只有第二版可保存为`topology.md`并进入后续。
8. 每版都先完成全部节点、分支、汇合和终点，但暂不编号。结构冻结后再按程序显示顺序统一编号：从入口向右逐层推进，同一层按父节点的选项顺序从上到下排列；一个分支必须从起点到终点保持自身上下位置，选择节点也按所在层编号。禁止先编号主线、再把支线编号补到全图末尾。随后生成正式`topology.md`与`mainline-path.json`，把每个主线切片一一映射到最终`episode-id`。主要终点的互动类型只能写`主要正式结局`或`主要失败结局`；动态终点写`独立小结局`。
   - 选择节点必须停在决定尚未执行处；其梗概不得先完成任何一个选项。
   - 独立小结局可以由来源选择直接抵达。主要正式或主要失败结局不得由选择直接抵达：每条主要结局路线至少先经过一个该路线独有的非结局发展节点。
   - 禁止一个三选或更多选择的全部后继都是终点，禁止把主要结局做成末端结局菜单。
   - 多个主要结局不得由同一个选择节点一次性完成分配。对每个主要结局计算“锁定选择”：该选项执行后只剩这一个主要结局可达，而执行前仍有多个主要结局可达。全部主要结局的锁定选择必须分布在至少两个不同选择节点；在同一个选择后为每条路线补普通节点、延长路线或改标题仍视为同一次结局分配，必须FAIL。
   - 至少两个独立小结局必须来自至少两个不同的真实决定裂缝；数量不足时退回主线故事重新设计真实决定情境，不得在同一裂缝或拓扑末端补数。
7. 生成`route-duration.json`，记录每个节点的预计可演分钟数，并枚举入口到全部结局的路径时长。任何路线不得超过上游规定的单次游戏时长上限；主线不是长度上限，支线允许比主线更长。
8. 按正式拓扑生成`emotional-spine.json`，把此前主干情绪运动投影到每个实际节点；带选择节点必须对应真实拐点。把规范化情绪脊SHA-256写入拓扑机器注释。
9. 生成梗概前完整读取`references/story-to-episode-synopsis.md`，按冻结拓扑一次生成全部`episode-synopses/<episode-id>.json`。`mainline-path.json`中的主线分集梗概必须逐字等于对应`source_text`，只能增加标题、冲突和拓扑字段；不得改写、扩写或摘要主线原文。支线梗概才从对应支线事实中生成。
   - 梗概进入正文时必须展开为人物当场可见、可听、可执行的动作、阻力与结果；不得把梗概压成概念陈述、账目式记录、作者判断或信息摘要。
9. 对全体梗概做一次整体拆解复检并封存`synopsis-set-review.json`：确认完整覆盖故事、顺序正确、没有遗漏或重复、分支不串线、汇合有共同事实、结局承接对应路线、各集推进量不过度失衡。

### 门禁

```bash
python3 scripts/build_stage_two_input.py <缓存目录> --output <缓存目录>/stage-two-input.json
python3 scripts/validate_emotional_movement.py <缓存目录>/unnumbered-emotional-movement.json --stage-two-input <缓存目录>/stage-two-input.json
python3 scripts/mainline_story_gate.py packet <缓存目录> --output <临时主线复检包.json>
python3 scripts/mainline_story_gate.py seal <缓存目录> <主线复检结果.json>
python3 scripts/mainline_story_gate.py verify <缓存目录>
python3 scripts/decision_fissure_gate.py packet <缓存目录> --output <临时决策裂缝复检包.json>
python3 scripts/decision_fissure_gate.py seal <缓存目录> <决策裂缝复检结果.json>
python3 scripts/decision_fissure_gate.py verify <缓存目录>
python3 scripts/story_treatment_gate.py packet <缓存目录> --output <临时完整故事复检包.json>
python3 scripts/story_treatment_gate.py seal <缓存目录> <完整故事复检结果.json>
python3 scripts/story_treatment_gate.py verify <缓存目录>
python3 scripts/validate_mainline_projection.py <缓存目录> --decomposition-only
python3 scripts/validate_topology_revision.py <缓存目录>/topology-draft-1.md <缓存目录>/topology.md
python3 scripts/validate_topology.py <缓存目录>/topology.md --movement <缓存目录>/unnumbered-emotional-movement.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_story_topology.py <缓存目录>/story-treatment.json <缓存目录>/topology.md --expected-endings E
python3 scripts/validate_route_duration.py <缓存目录>/route-duration.json <缓存目录>/topology.md <缓存目录>/stage-two-input.json
python3 scripts/validate_emotional_spine.py <缓存目录>/emotional-spine.json
python3 scripts/validate_emotional_topology.py <缓存目录>/topology.md --spine <缓存目录>/emotional-spine.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/synopsis_set_gate.py packet <缓存目录> --output <临时梗概集合复检包.json>
python3 scripts/synopsis_set_gate.py seal <缓存目录> <梗概集合复检结果.json>
python3 scripts/synopsis_set_gate.py verify <缓存目录>
```

全部命令PASS后，线性主线、决策裂缝审计、支线故事图、拓扑、路线时长和全体梗概一起冻结，才允许写任何分集正文。PASS至少代表：主线是一篇无分支可能性语言的完整故事；全篇真实决定裂缝已扫描，任何因果充分的提前结局动作都被采用，较弱汇合选择没有替代它；全图至少有2个独立小结局，它们可以是放弃、偏航、离场、关系断裂、错过时机或其他使角色不再合理返回当前核心故事的收束，不要求死亡；支线没有改写主线，可短于、等于或长于主线；每次选择后先判断是否已经形成结局；所有入口到结局路线均不超过上游单次游戏时长；确定节点数来自全部路线的因果展开；拓扑编号连续且符合从左到右、同层从上到下的程序显示顺序，入口唯一、全部节点可达、无环、无断头；全体梗概完整覆盖主线与支线并且每集形成因果变化。

命令中的`E`、`F`、`X`只表示上游主要结局总数、主要正式结局数和主要失败结局数；动态独立小结局不计入三者，拓扑实际终点总数允许大于`E`。

## 阶段三：逐集剧本写作与逐集放行

### 读取

- 单集切片只读取`references/episode-story-adapter.md`与脚本生成的适配源
- Screenwriter只读取`references/vimax-screenwriter.md`和当前连续故事输入
- Enhancer只读取脚本生成的`enhancer-inputs/<episode-id>.txt`；该文件必须逐字包含`vimax-script-enhancer.md`、`chinese-dialogue-craft.md`、当前Screenwriter草稿和停止边界
- Screenwriter原稿完成后，才读取`references/character-appearance-validation.md`提取首次出场证据
- 当前题材标签命中`references/genre-direction.md`中的模块时读取该文件；否定标签不得误触发，未命中时不增加题材义务
- 当前集出现推动剧情的书面信息时，再读取`references/written-text-to-dialogue.md`

### 隔离工作集

阶段三开始时，按冻结拓扑把相邻因果节点划成不超过3集的工作批次。共同主线、不同分支、汇合段和结局段分别成批；不得把互斥路线正文放进同一活跃工作集。批次不改变拓扑和正式输出。每集内部只分适配、编剧、Enhancer三个互不共享多余材料的工作区。

- 同一时刻只写当前一集。不得先生成整批正文，再回头补验收。
- 适配工作区可读取当前梗概、当前节点、已放行直接前置真实结尾、相关人物资产、世界规则和直接后续梗概，只负责生成连续故事与一句停止边界。
- 编剧工作区只能读取通过门禁的`episode-writing-inputs/<episode-id>.txt`、Screenwriter reference和中文台词reference；增强工作区只能读取`enhancer-inputs/<episode-id>.txt`。该输入由脚本绑定当前草稿、停止边界、Enhancer reference和完整中文台词reference，缺一不可。
- 情绪脊、完整故事、验证脚本、证据格式、旧稿与审核意见不得进入编剧或Enhancer工作区。
- 已放行的更早正文保留在缓存中作为证据，但退出活跃工作集；除定位连续性问题外，不得重新通读或复制进当前写作上下文。
- 每完成一批，确认增强稿已经逐字装入正式正文并通过确定性结构门禁，再切换到下一批。切换后不再把草稿、淘汰方案和无关路线材料纳入活跃工作集。

### 每集循环

按上述批次顺序执行，批次内仍按冻结拓扑的拓扑序一次只处理一集；当前集的全部直接前置分集必须已经通过：

1. 运行`build_episode_adaptation_source.py`建立`episode-adaptation-sources/<episode-id>.json`。该源不读取、依赖或生成过程链。
2. 按`episode-story-adapter.md`比较当前集与直接后续的动作所有权，生成`episode-story-materials/<episode-id>.json`。当前集只保留自己的变化；后续若以同一动作作为主要冲突、完整核验或选择，当前集只能建立前提或已有状态。
3. 运行`build_episode_writing_input.py`。只有材料为二至六个连续自然段、没有清单和验收术语、停止边界有效时，才输出`episode-writing-inputs/<episode-id>.txt`。
4. 把Screenwriter放入隔离工作区，只给当前写作输入、`vimax-screenwriter.md`和台词reference，生成`screenplay-drafts/<episode-id>.md`。不得附加角色卡、过程链、预期出口、审核问题或旧稿。随后运行`validate_screenwriter_draft.py`；原稿未实际形成可表演场景、含占位或制作元话语、没有动作—反馈—调整、没有局面变化，均不得进入Enhancer。该门禁只验收Screenwriter是否履职，不润色或重写正文。
5. Screenwriter门禁PASS后才允许运行`build_enhancer_input.py`，把当前草稿、停止边界、`vimax-script-enhancer.md`与`chinese-dialogue-craft.md`逐字组装为`enhancer-inputs/<episode-id>.txt`。`build_enhancer_input.py`必须验证同一草稿的PASS回执及SHA-256，不能仅凭文件非空放行。隔离Enhancer只读取该文件，一次性生成`enhanced-screenplays/<episode-id>.md`。Enhancer可以完整改写场面表达、全部对白、话轮、停顿、反应和不改变因果的动作组织，不要求保留草稿原句；禁止改变冻结剧情事实、人物行动结果、选择、结局或停止边界。
6. 把增强稿原样装入`episodes/<episode-id>.md`，冻结梗概与九字段保持原样。正文区必须与`enhanced-screenplays/<episode-id>.md`逐字一致。增强稿完成后才读取首次出场规则并提取证据。
7. 只运行当前集确定性结构门禁，检查九字段、拓扑关系、资产白名单、增强稿逐字一致、角色首次出场与停止边界绑定。取消写后过程检查和普通观众冷读，不再生成场面展开计划、过程复检包、质量复检包或相关回执，也不让验收逻辑触碰增强稿质感。

### 当前集门禁

```bash
python3 scripts/build_episode_adaptation_source.py <缓存目录> <分集编号> --output <缓存目录>/episode-adaptation-sources/<分集编号>.json
python3 scripts/build_episode_writing_input.py <适配源.json> <连续故事材料.json> <分集编号> --output <缓存目录>/episode-writing-inputs/<分集编号>.txt
python3 scripts/validate_screenwriter_draft.py <缓存目录>/screenplay-drafts/<分集编号>.md --episode-id <分集编号> --receipt <缓存目录>/screenwriter-receipts/<分集编号>.json
python3 scripts/build_enhancer_input.py <缓存目录>/screenplay-drafts/<分集编号>.md --boundary "<停止边界>" --enhancer-reference references/vimax-script-enhancer.md --dialogue-reference references/chinese-dialogue-craft.md --screenwriter-receipt <缓存目录>/screenwriter-receipts/<分集编号>.json --output <缓存目录>/enhancer-inputs/<分集编号>.txt
python3 scripts/validate_episode.py <缓存目录> <分集编号>
```

每集通过必须同时满足：连续故事材料绑定当前冻结梗概；编剧输入没有清单、证据或内部结构；增强稿正文与正式候选逐字一致；九字段结构、拓扑、资产、首次出场和停止边界一致。写完全部分集后直接进入阶段四。

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
python3 scripts/validate_mainline_projection.py <缓存目录>
python3 scripts/validate_character_appearances.py <缓存目录> --asset-catalog <缓存目录>/asset-catalog.json --introductions <缓存目录>/character-introductions.json
```

全部PASS后，只能用业务组装器生成结果：

```bash
python3 scripts/assemble_business_output.py <缓存目录> <输出目录>/episode-business.json --completion-receipt <输出目录>/completion-receipt.json --handoff <输出目录>/episode-handoff.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_business_output.py <输出目录>/episode-business.json --asset-catalog <缓存目录>/asset-catalog.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/verify_deliverable.py <缓存目录> <输出目录>/episode-business.json <输出目录>/completion-receipt.json <输出目录>/episode-handoff.json --expected-endings E --expected-formal F --expected-failure X
```

组装器只能映射已验证内容，不得新增、改写或摘要剧本。组装器必须原子生成业务JSON、`completion-receipt.json`和`episode-handoff.json`；业务JSON或任一绑定依赖变化时，完成凭证与交接清单立即失效。`validate_business_output.py`只验证九字段接口与图结构，成功输出`STRUCTURE_PASS`和`NOT_A_COMPLETION_ATTESTATION`，绝不代表本Skill完成。只有`verify_deliverable.py`重新执行全部组装检查、重算业务结果并输出`DELIVERABLE_ACCEPTED`，才允许把业务JSON交给下游、声称分集完成或最终验收通过；缺任一文件或验收失败时不得输出正式分集slot。一次性返回完整`分集列表`JSON；不得返回局部节点或内部材料。

## 修改已有结果

- 用户在已有分集结果上新增、插入、删除、重连或实质改写节点时，优先进入`references/local-node-editing.md`定义的用户局部编辑模式；当前节点关系和用户修改是事实源，不退回阶段二重新评价该改动是否符合原情绪脊。
- 自动生成阶段自行发现完整故事或拓扑错误，仍按最早失效阶段返修；不得把这种内部返修规则套到用户已经明确执行的局部编辑上。
- 改上游事实：重新执行阶段一，并使受影响的阶段二、三、四失效。
- 非用户局部编辑模式下改完整故事中的事件、节点、边、条件、选择或结局：解冻阶段二，从最早受影响材料重新执行，使受影响正文和全部下游回执失效。
- 只改某集梗概或本集因果且拓扑不变：同步修改完整故事对应段落和授权梗概，重新通过完整故事、故事—拓扑及梗概集合门禁；未授权梗概与正文保持不变，再重写受影响正文。
- 只改某集正文表达或对白且冻结梗概不变：以修改前缓存作为`--baseline-root`，逐个用`--allowed-changed <episode-id>`授权；未授权分集必须逐字不变，完整故事、拓扑和梗概集合必须不变。
- 只改对白：增加`--change-scope dialogue`；授权分集内的非台词内容、事实、动作、状态、选择和结尾也不得变化。
- 创建、修改、重做和恢复都返回当前完整结果，不只返回变化片段。

详细参数和失效范围读取`references/run-basis-and-stage-gates.md`中的修改模式。不得因为局部修改而跳过受影响分集的确定性结构验收。

## 完成条件

以下条件全部成立才算完成：

- 阶段一和阶段二门禁全部PASS，拓扑已冻结。
- 无条件分支语言的线性主线故事已冻结；支线故事与正式拓扑都绑定该主线，主线路径可辨认但不限制其他路线长度。
- 全体分集梗概已完整覆盖故事并整体冻结，不存在遗漏、重复、串线或明显失衡。
- 每集都独立完成一次Screenwriter草稿、一次Enhancer增强和确定性结构验收；增强稿原样成为正式正文，不再执行写后过程检查、普通观众冷读或生成第三版正文。
- 所有梗概都先于任何完整剧本通过集合门禁，且不存在正文反向改写冻结梗概。
- 用户意图、全路径首次出场和全体逐集结构门禁全部PASS。
- 正式JSON严格符合九字段合同，分集数等于冻结拓扑节点数。
- 第一项是具有非空完整剧本的`episode-001`。
- 每个有效选择只在来源分集`互动节点`中出现一次。
- 组装后的业务JSON再次通过独立业务校验。
- 最终对外只返回完整业务JSON，不包含内部过程或其他工程结构。
