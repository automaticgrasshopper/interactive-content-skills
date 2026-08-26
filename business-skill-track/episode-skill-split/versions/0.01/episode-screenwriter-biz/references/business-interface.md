# 业务接口声明

本文件是分集剧情 Skill 与调用方之间的唯一字段合同。编剧方法见`node-screenwriting.md`，对白和质量要求见`dialogue-and-quality.md`；本文件只声明冻结依赖、单节点输入输出和写入边界。

## 接口规则

- 只消费流程图 Skill 已正式验收的路线对象，一次只处理一个指定`node_id`。
- 路线版本、路线哈希或节点材料哈希不一致时立即返回依赖错误，不得自行重建路线。
- 只读取当前节点、直接前情、入口状态、允许资产和`stop_boundary`。
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
- 正文必须包含可拍摄场次、动作和对白，并停在当前`stop_boundary`内。
- 创作分析、展开计划、连续性、冷读问题和验收结论必须来自当前正式正文，禁止登记句、梗概复述和抽象占位文字。
- `关联角色`、`关联场景`和`关联道具`只记录正文实际出现且属于路线白名单的正式名称。
- `quality_checks`至少覆盖路线忠实、停止边界、连续性、对白和资产一致性；每项证据必须能在正文中逐字定位。
- 补丁不得包含`nodes`、`edges`、`choices`、`endings`、标题、梗概、连接、互动节点、结局、路线状态变化或停止边界。

## 九字段兼容投影

- 本 Skill 独占写入`分集剧本.完整剧本`及正文实际出现的`关联角色`、`关联场景`、`关联道具`。
- `剧本创作分析`是剧本生成后产生的独立字段，不覆盖路线侧原`剧本分析`。
- 路线侧的分集身份、标题、梗概、冲突、前后连接、结局和互动节点只读，不允许修改。

## 完成边界

只有`accept_node_screenplay.py`输出`NODE_SCREENPLAY_ACCEPTED`并写出当前节点补丁后才算完成。失败时不得写补丁，也不得影响正式路线、其他节点或已验收节点。
