# 业务接口声明

本文件是分集剧情 Skill 与调用方之间的唯一字段合同。编剧方法见`node-screenwriting.md`，对白和质量要求见`dialogue-and-quality.md`；本文件只声明冻结依赖、单节点输入输出和写入边界。

用户界面阶段播报见`user-visible-progress.md`。阶段播报是临时展示文本，不属于输入输出合同，不得写入路线、节点补丁、剧本正文或创作分析。

## 接口规则

- 只消费流程图 Skill 已正式验收的路线对象，一次只处理一个指定`node_id`。
- 路线版本、路线哈希或节点材料哈希不一致时立即返回依赖错误，不得自行重建路线。
- 只读取当前节点、直接前情、入口状态、允许资产和`stop_boundary`。
- 当前节点必须由`episode-route-planner-biz/0.02`生产。重要人物行动节点在`entry_state.dramatic_pressure`和`state_changes.dramatic_effect`中同时提供完整双因果；只出现其中一个时返回路线依赖错误。两者都未提供表示本节点是纯功能过桥，分集编剧不得为它补造情感转折。
- 输出只写入对应节点的剧本区域，不提交或覆盖整个路线。
- 每个节点独立生成、验收和保存；当前节点失败不得影响路线或其他节点。

## Skill 输入字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `正式路线` | object | 是 | `nextplay.episode-route-handoff.v1`对象，且`route_status=accepted`、整体哈希和节点哈希有效。 |
| `project_id` | string | 是 | 必须与正式路线一致。 |
| `route_id` | string | 是 | 必须与正式路线一致。 |
| `route_version` | string | 是 | 必须与正式路线一致。 |
| `route_output_hash` | string | 是 | 必须与正式路线一致。 |
| `node_id` | string | 是 | 本轮唯一允许写入的节点。 |
| `node_route_material_hash` | string | 是 | 必须与目标节点一致。 |
| `直接前情节点` | list<object> | 是 | 只包含目标节点直接前驱的已冻结路线事实和必要结尾；入口节点允许为空。 |
| `当前节点停止边界` | string | 是 | 必须逐字等于目标节点`route_material.stop_boundary`。 |
| `允许角色与资产` | object | 是 | 只能是目标节点路线材料中的白名单。 |

`允许角色与资产`以`nextplay.episode-screenwriting-context.v1`对象传入，字段固定为：

```text
contract_version
project_id / route_id / route_version / route_output_hash
node_id / node_route_material_hash
characters[] = {name, public_identity, identity_anchor, current_relevance, relationship_context?, speech_profile?}
scenes[] = {name, public_description}
props[] = {name, public_description}
direct_predecessor_endings[] = {node_id, ending_excerpt}
```

- 三类资产名称必须与当前节点白名单分别完全一致，不得多传或漏传。
- `public_identity`说明观众可知的身份，`identity_anchor`是帮助写作者识别身份交代是否成立的最短语义锚（如“记者”“东闸现场负责人”），`current_relevance`说明人物为何与当前任务有关；三者缺一不得开始写作，不得只凭角色名猜职业、权限或关系。正文必须让普通观众理解同一身份事实，但不要求逐字复述`identity_anchor`，可以由正在做的事、权限、自然称呼和他人反应共同完成。
- 入口节点的`direct_predecessor_endings`为空；其他节点必须与直接前置编号完全一致，并提供真实正文结尾。
- 场景与道具说明只提供冻结的可见属性和已知用法，不授权模型发明按钮、灯号、操作流程或审核字段。
- 冻结写作包同时包含当前节点只读的`互动节点`合同，使分支来源节点能知道每个真实行动；不得把全图规划理由带入写作。
- `dramatic_pressure={fact_trigger, felt_meaning}`说明外部发生了什么及人物怎样理解；`dramatic_effect={resulting_action, human_change, later_effect}`说明因此采取的行动、人物或关系变化，以及该变化留下的后续行为约束。正文不照念这些字段，只把它们变成可见行动、回应、拒绝、隐瞒、承担或关系距离。

## Skill 输出字段

```text
单节点补丁 object
├─ contract_version string
├─ capability_id string
├─ skill_version string
├─ project_id string
├─ route_id string
├─ route_version string
├─ route_output_hash string
├─ node_id string
├─ node_route_material_hash string
├─ screenplay object
│  ├─ 分集剧本 object
│  │  └─ 完整剧本 string
│  ├─ 剧本创作分析 object
│  │  ├─ 创作分析 string
│  │  ├─ 场景和段落展开计划 string
│  │  ├─ 连续性分析 string
│  │  ├─ 冷读与质量问题 string
│  │  └─ 验收结论 "PASS"
│  ├─ 关联角色 list<string>
│  ├─ 关联场景 list<string>
│  ├─ 关联道具 list<string>
│  ├─ 派生信息 object
│  └─ quality_checks list<object>
│     └─ {check, passed, evidence}
├─ screenplay_hash string
├─ status "accepted"
└─ accepted_at string
```

## 输出约束

- `contract_version`固定为`nextplay.episode-node-patch.v1`，`capability_id`固定为`episode-screenwriter-biz`。
- 正文必须包含可拍摄场次和实际动作，并停在当前`stop_boundary`内。对白只在人物确有交流或自言需要时出现，不得为了合同验收强行开口。
- 创作分析、展开计划、连续性、冷读问题和验收结论必须来自当前正式正文，禁止登记句、梗概复述和抽象占位文字。
- `关联角色`、`关联场景`和`关联道具`只记录正文实际出现且属于路线白名单的正式名称。
- `quality_checks`至少覆盖路线忠实、停止边界、连续性、首次出场、空间与动作连续、非台词场面化和资产一致性；路线材料提供双因果时再覆盖双因果，正文含对白时再覆盖对白，分支来源节点再覆盖`choice_readiness`，且每个冻结选项至少有一条不同的正文证据。每项只引用正文已经自然存在的最小证据；不得为了凑检查项扩写正文。
- 补丁不得包含`nodes`、`edges`、`choices`、`endings`、标题、梗概、连接、互动节点、结局、路线状态变化或停止边界。

## 九字段兼容投影

- 本 Skill 独占写入`分集剧本.完整剧本`及正文实际出现的`关联角色`、`关联场景`、`关联道具`。
- `剧本创作分析`是剧本生成后产生的独立字段，不覆盖路线侧原`剧本分析`。
- 路线侧的分集身份、标题、梗概、冲突、前后连接、结局和互动节点只读，不允许修改。

## 完成边界

只有`accept_node_screenplay.py`输出`NODE_SCREENPLAY_ACCEPTED`并写出当前节点补丁后才算完成。失败时不得写补丁，也不得影响正式路线、其他节点或已验收节点。
