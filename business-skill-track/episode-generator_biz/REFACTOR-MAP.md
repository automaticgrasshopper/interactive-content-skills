# episode-generator 业务版重构对照

本文件位于可部署 Skill 快照之外，用于证明 `episode-generator_biz` 的模板化重构没有删减原有业务能力。

## 版本轨道

- `0.01`：首个业务协作快照，保留当时的调用期外层合同。
- `0.02`：对齐网页现有 `_biz` Skill 的业务接口格式；不覆盖、不合并 `0.01`。
- `0.03`：以通用 `v0.1.51` 的完整流程为业务内核，增加工程接口与确定性业务 JSON 适配；同时保留首集分支的轻量空开场兜底，不覆盖、不合并 `0.02`。
- 通用验证引擎同步升级为 `v0.1.51`；旧逐集质量回执仍按正文和 Reference 指纹判断，不因版本号单独失效。

网页在 2026-07-29 当前可见的全部 `_biz` Skill 共三个：

1. `outline-generator_biz`
2. `asset-designer_biz`
3. `asset-image-generator_biz`

三者共同使用根目录 `SKILL.md`、`agents/openai.yaml`、`references/business-interface.md`和按职责拆分的内容规则；平台下载中的`manifest.json`、`current.json`、`history.jsonl`属于发布层元数据，不复制进业务源码快照。

## 标识边界

- 通用 Skill：`episode-generator`
- 业务平台 slug：`episode-generator_biz`
- Skill 内部标准名称：`episode-generator_biz`
- 当前业务协作快照：`0.03`
- 唯一工程字段合同：`0.03/references/business-interface.md`
- 精确内容结构：`0.03/references/episode-output-schema.md`
- 当前通用验证引擎：`v0.1.51`

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
| `episode-001`为分支时的两行、60字符实质剧情和制作话术拦截 | `validate_business_output.py` |
| 十字段及子字段、分集数、选择、前后节点、结局、场次格式 | `validate_business_output.py` |
| 未授权分集不变、对白范围内非台词不变、拓扑不变 | `validate_business_output.py` |
| 三份公开文件确定性投射与整组事务提交 | `references/technical-handoff.md` 和技术 adapter |

## 输出字段锁

`0.02`起按网页 `_biz` 共同格式，`0.03`继续保持正式结果顶层只含：

- `分集结构`：保留节点类型、结局标记、梗概和可见跳转。
- `分集列表`：每集严格使用十字段及全部子字段；新增的`分集数`等于冻结拓扑后的实际节点总数，并在所有分集对象中一致。

不再把`合同版本`、`状态`、`动作`、`本轮变更`、`保持不变`、`工具结果`、`待确认问题`、`警告`或`错误`包进正式业务 JSON。这些属于调用控制或运行时错误通道，不是 Sheet3 业务字段，也不应进入数据库或玩家界面。

情绪脊、资产索引、首次出场证据、门禁状态、缓存、哈希和复检回执继续用于内部强验证，但不进入正式业务字段。删除外层包装只调整接口边界，不删除任何生成或验证门禁。
