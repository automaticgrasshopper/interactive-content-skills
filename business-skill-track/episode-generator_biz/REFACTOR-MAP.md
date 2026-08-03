# episode-generator 业务版重构对照

本文件位于可部署 Skill 快照之外，用于证明业务版分集 Skill 的模板化重构没有删减原有业务能力。

## 版本轨道

- `0.01`：首个业务协作快照，保留当时的调用期外层合同。
- `0.02`：对齐网页现有 `_biz` Skill 的业务接口格式；不覆盖、不合并 `0.01`。
- `0.03`：以通用 `v0.1.51` 的完整流程为业务内核，增加工程接口与确定性业务 JSON 适配；同时保留首集分支的轻量空开场兜底，不覆盖、不合并 `0.02`。
- `0.04`：以通用 `v0.1.52` 为完整业务内核，新增`选择数`和剧集／选择双节点交付拓扑，建立用户明确要求优先级与对外输出防火墙；不覆盖、不合并 `0.03`。
- `0.05`：以通用 `v0.1.53` 为完整业务内核，只新增私有用户意图合同、冲突 AskUser 门禁、独立履约证据及回执绑定；不改变 `0.04` 已确认的生成和验证能力，不覆盖、不合并 `0.04`。
- `0.06`：继续完整使用通用 `v0.1.53` 内核；选择只在`分集列表[].互动节点`保存一次，`分集结构`只列剧集节点，禁止重复物化`choice-xxx`，避免前端再次派生后出现无连接的重复选择卡片；不覆盖、不合并 `0.05`。
- `0.07`：继续完整使用通用 `v0.1.53` 内核和`0.06`单一选择事实源；新增对外消息防火墙，默认不发送过程消息，平台强制需要状态时只允许`正在生成中`，并要求技术 UI 丢弃其他内部过程状态；不覆盖、不合并 `0.06`。
- `0.08`：继续完整使用通用 `v0.1.53` 内核；纠正`0.06/0.07`的节点投射方向，恢复剧集／选择双节点交付，但强制所有非结局`episode-xxx`为`剧集节点/剧情节点`，仅`choice-xxx`可显示选择；增加完成态提交屏障、同源选择唯一性和整组替换约束，同时继承`0.07`静默优先的消息防火墙；不覆盖、不合并 `0.07`。
- `0.09`：继续完整使用通用 `v0.1.53` 内核；对齐 2026-08-01 Sheet3 最新十一字段，删除`选择数`，把`选择节点`和`互动节点`拆成两个一级字段。`分集数`固定表示互动节点总数；每个分集恰好一个互动节点，每个有效选择只在对应分集的选择节点字段中封装一次；不覆盖、不合并 `0.08`。
- `0.10`：继续完整使用通用 `v0.1.53` 内核与 0.09 十一字段；根据真实线上回放，把每条`分集列表`记录固定为互动节点身份：`互动节点.是否为互动节点=true`、`选择节点.是否为选择节点=false`，是否存在后续选择只由`是否有选择问题`及互动连线表达。新增身份互斥强门禁，并强制第一条记录为有完整剧情的`episode-001`，避免带选择的分集被再次投射成选择卡以及首集剧情卡消失；不覆盖、不合并 `0.09`。
- `0.11`：继续完整使用通用 `v0.1.53` 内核和 0.10 十一字段；根据 0.10 线上双端回放，确认业务 JSON 正确但临时路线脚本把boolean与字符串`是`比较，导致互动与结局标记失真。新增唯一确定性路线投影器和业务 JSON—route.json 交叉校验器，禁止临时手写投影；强验证首个剧情节点、剧情/选择/可视节点数量、choice/default边、目标、结局和全图可达性；不覆盖、不合并 `0.10`。
- `0.12`—`0.14`：继续完整使用通用 `v0.1.53` 内核，逐步稳定路线节点编号、入口剧情渲染、选择节点展示与线上兼容性；历史快照保持不变。
- `0.15`：对齐当前工程路线合同，剧情节点使用`node_type=video`、选择节点使用`node_type=choice`，移除工程合同未声明的`route.settings`；投影器与交叉校验器同步采用同一规则。Skill 标准名称及上传目录由`episode-generator_biz`改为`episode-generator-biz`。业务十一字段、情绪脊、拓扑、逐集写作、语义审核和玩家可见路线均不改变；不覆盖、不合并`0.14`。
- 通用验证引擎同步升级为 `v0.1.53`；版本号本身仍不使回执失效，只有正文、Reference、用户要求源、用户意图合同或回执合同变化才会失效。

网页在 2026-07-29 当前可见的全部 `_biz` Skill 共三个：

1. `outline-generator_biz`
2. `asset-designer_biz`
3. `asset-image-generator_biz`

三者共同使用根目录 `SKILL.md`、`agents/openai.yaml`、`references/business-interface.md`和按职责拆分的内容规则；平台下载中的`manifest.json`、`current.json`、`history.jsonl`属于发布层元数据，不复制进业务源码快照。

## 标识边界

- 通用 Skill：`episode-generator`
- 业务平台 slug：`episode-generator-biz`
- Skill 内部标准名称：`episode-generator-biz`
- 当前业务协作快照：`0.15`
- 唯一工程字段合同：`0.15/references/business-interface.md`
- 精确内容结构：`0.15/references/episode-output-schema.md`
- 路线投影合同：`0.15/references/route-projection-contract.md`
- 当前通用验证引擎：`v0.1.53`

四者独立管理，不互相替代。

## 输入字段锁

| 原输入 | 新版去向 | 状态 |
| --- | --- | --- |
| 游戏企划 | `business-interface.md`、`input-and-conflict-rules.md` | 保留 |
| 角色描述 | `business-interface.md`、`input-and-conflict-rules.md` | 保留 |
| 场景描述 | `business-interface.md`、`input-and-conflict-rules.md` | 保留 |
| 道具描述 | `business-interface.md`、`input-and-conflict-rules.md` | 保留 |
| 已有分集结果与允许修改范围 | `business-interface.md`、`modification-audit-rules.md` | 保留 |

## 生成链对照

| 原能力 | 新版载体 |
| --- | --- |
| 上游压缩、冲突处理、正式资产冻结 | `input-and-conflict-rules.md`、`generation-workflow.md` |
| 用户明确要求锁定、前后冲突 AskUser、独立履约证据 | `user-intent-lock.md`、`validate_user_intent_lock.py` |
| 状态变量只为后续条件和结局服务 | `generation-workflow.md` |
| 体量映射结构引擎 | `emotional-spine-and-topology.md` |
| 节点建议区间为可选软约束，缺失不阻塞拓扑 | `upstream-input-translation.md`、`emotional-spine-state-graph.md` |
| PAD/VAD 主干情绪脊 | `emotional-spine-and-topology.md` |
| 从真实情绪拐点识别岔点 | `emotional-spine-and-topology.md` |
| 开扇、独立结果、带差异合流、收扇 | `emotional-spine-and-topology.md` |
| 互动密度、结局落点、情绪验收 | `emotional-spine-and-topology.md` |
| 冻结拓扑后逐路径写作 | `generation-workflow.md`、`episode-writing-rules.md` |
| 相邻因果拍、完整场面、软篇幅 | `episode-writing-rules.md` |
| 中文自然台词与两步轻量复写 | `dialogue-rules.md` |
| 画内文字转可听对白 | `written-text-rules.md` |
| 正式角色覆盖和全路径首次出场 | `character-continuity-rules.md` |
| 逐集冷读理解门和七项复检 | `episode-quality-review.md` |
| 局部修改、对白范围和拓扑锁定 | `modification-audit-rules.md` |

## 强验证对照

| 原门禁 | 新版载体 |
| --- | --- |
| 唯一入口、全节点可达、无环、可达结局 | `validate_topology.py` |
| 情绪脊合同、范围、顺序、拐点、哈希、结局数量 | `validate_emotional_topology.py` |
| 资产合同、重名、别名、角色覆盖、首次出场证据 | `validate_character_appearances.py` |
| 理解门、七项覆盖、正文与 Reference 指纹回执 | `episode_quality_gate.py` |
| 用户要求源、合同、创作物和逐项履约证据绑定 | `validate_user_intent_lock.py`、`episode_quality_gate.py` |
| `episode-001`为分支时的两行、60字符实质剧情和制作话术拦截 | `validate_business_output.py` |
| 十一字段及子字段、互动节点数、选择单一事实源、前后节点、结局、场次格式 | `validate_business_output.py` |
| 互动／选择编号域、节点类型与一入多出投射 | `validate_business_output.py` |
| 每个分集恰好一个互动节点、互动／选择身份互斥、同一来源恰好封装一个选择 | `validate_business_output.py` |
| 业务 JSON 与路线节点等长同序、入口先剧情、选择只投影一次、boolean类型正确 | `build_route_projection.py`、`validate_route_projection.py` |
| choice/default边、目标、结局标记、剧情可达和结局可达 | `validate_route_projection.py` |
| 未授权分集不变、对白范围内非台词不变、拓扑不变 | `validate_business_output.py` |
| 三份公开文件确定性投射与整组事务提交 | `references/technical-handoff.md` 和技术 adapter |

## 输出字段锁

`0.15`继续沿用 Sheet3 最新格式，正式结果顶层只含`分集列表`。每集严格使用十一字段及全部子字段：`分集数`等于互动节点总数并在所有分集对象中一致；分集记录固定为互动节点身份；`选择节点`字段只封装播完本集后的可选问题、选项文字与目标互动节点，不把当前分集再次标为选择节点。路线提案只由内置投影器从该结果生成；`选择数`和重复的`分集结构`不属于正式业务字段。

不再把`合同版本`、`状态`、`动作`、`本轮变更`、`保持不变`、`工具结果`、`待确认问题`、`警告`或`错误`包进正式业务 JSON。这些属于调用控制或运行时错误通道，不是 Sheet3 业务字段，也不应进入数据库或玩家界面。

用户要求源、用户意图合同、冲突解决记录、履约证据、情绪脊、资产索引、首次出场证据、门禁状态、缓存、哈希和复检回执继续用于内部强验证，但不进入正式业务字段。删除外层包装只调整接口边界，不删除任何生成或验证门禁。
