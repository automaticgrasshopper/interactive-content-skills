# 业务接口声明

本文件是流程图 Skill 与调用方之间的唯一字段合同。路线方法见`route-planning-method.md`，验收语义见`route-acceptance.md`；本文件只声明输入、输出和写入边界。

## 接口规则

- 初次生成读取正式项目身份、`游戏企划`、`角色描述`、`场景描述`和`道具描述`。
- 正式输出是可立即展示、编辑和保存的路线对象，不依赖任何节点剧本。
- 节点、边、选择和结局均由本 Skill 生产；调用方不得用剧本补丁反向覆盖这些事实。
- 角色、场景和道具只使用上游正式名称或已登记别名，不输出资产工程 ID。
- 哈希、验收时间和路线状态是交接字段；规划草稿、复检记录和修复过程是内部数据，不进入正式输出。
- 任一路线门禁失败时不得返回可被当作正式流程图的对象。

## Skill 输入字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `manifest.json` | object | 是 | 正式或测试项目身份；至少提供唯一`project_id`及本轮可读资产范围。测试时可由调用方依据用户输入构造，但不得冒充已有线上项目。 |
| `游戏企划` | object | 是 | 包含标题、目标、冲突、世界观、体量、完整故事和结局方向；节点数量建议不作为固定约束。 |
| `角色描述` | list<object> | 是 | 至少包含主角及路线必需角色。 |
| `场景描述` | list<object> | 是 | 无正式场景时允许为空列表。 |
| `道具描述` | list<object> | 是 | 无关键道具时允许为空列表。 |
| `用户要求` | string | 否 | 本轮明确的路线约束；与正式输入冲突时先询问。 |

## Skill 输出字段

```text
路线对象 object
├─ contract_version string
├─ capability_id string
├─ skill_version string
├─ project_id string
├─ route_id string
├─ route_version string
├─ route_status "accepted"
├─ route_input_hash string
├─ route_output_hash string
├─ accepted_at string
├─ nodes list<object>
│  └─ 节点对象
│     ├─ node_id string
│     ├─ node_type "episode"
│     ├─ 分集标题 string
│     ├─ route_material object
│     │  ├─ 单集梗概 string
│     │  ├─ 本集冲突 string
│     │  ├─ entry_state object
│     │  ├─ state_changes object
│     │  ├─ allowed_characters list<string>
│     │  ├─ allowed_scenes list<string>
│     │  ├─ allowed_props list<string>
│     │  └─ stop_boundary string
│     ├─ 前置节点编号列表 list<string>
│     ├─ 后续节点编号列表 list<string>
│     ├─ 是否结局 boolean
│     ├─ ending_type string | null
│     ├─ 互动节点 object
│     │  ├─ 是否为分支节点 boolean
│     │  ├─ 是否有选择问题 boolean
│     │  ├─ 选择问题 string
│     │  ├─ 选项列表 list<object>
│     │  │  └─ {选项编号, 选项文字, 目标分集编号}
│     │  └─ 默认下一分集编号 string
│     └─ node_route_material_hash string
├─ edges list<object>
├─ choices list<object>
└─ endings list<object>
```

## 输出约束

- `contract_version`固定为`nextplay.episode-route-handoff.v1`，`capability_id`固定为`episode-route-planner-biz`。
- `route_status`必须为`accepted`；节点从`episode-001`开始连续编号，且只有一个入口。
- 图必须可达、无环并最终抵达结局；边、选择和结局索引必须与节点内事实完全一致。
- 有选择的节点至少提供两个不同目标；普通节点只有一个默认后继；结局节点后继为空且默认后继为`无`。
- `ending_type`只允许`main`、`expected`、`failure`和`small`；非结局为`null`。
- `route_material`必须足以支持下游写作，并明确当前节点的状态变化、资产白名单和`stop_boundary`。
- 承担重要人物行动、决定裂缝或人物关系后续消费的节点，必须同时提供`entry_state.dramatic_pressure={fact_trigger, felt_meaning}`与`state_changes.dramatic_effect={resulting_action, human_change, later_effect}`。这些是路线因果事实：分别说明外部刺激、人物如何理解、因此采取的行动、人物或关系变化，以及该变化对后续行为的影响；不得只填情绪标签或抽象主题。纯功能过桥节点可以不含这两个对象，但不得只写其中一个，也不得为满足格式硬造关系变化。
- 输出不得包含完整剧本、创作分析、对白、冷读、质量结论或占位正文。

## 九字段兼容投影

- 路线独占写入`分集编号`、`分集标题`、`分集剧本.单集梗概`、`剧本分析.本集冲突`、`剧本分析.前置节点编号列表`、`剧本分析.后续节点编号列表`、`是否结局`和`互动节点`。
- `分集剧本.完整剧本`及正文实际出现的`关联角色`、`关联场景`、`关联道具`由分集剧情 Skill 写入。
- 分集剧情 Skill 可以读取路线字段，但不得修改；调用方组合两个正式产物时不得产生第二套拓扑事实源。

## 完成边界

只有`workflow_state.py`逐步放行并完成两版独立拓扑与匿名一次择优，随后到达`ACCEPT_PLANNING`、规划门禁对当前缓存根输出`PLANNING_ACCEPTED`，且`accept_route.py CACHE_ROOT FORMAL_ROUTE.json`输出`ROUTE_ACCEPTED`并写出正式路线后才算完成。规划阶段文件、匿名映射和回执均为内部数据，不进入正式路线对象。完成后立即交给 UI 展示并结束，不得自动进入剧本生成。
