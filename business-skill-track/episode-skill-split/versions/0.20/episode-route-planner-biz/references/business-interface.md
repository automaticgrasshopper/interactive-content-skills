# 业务接口声明

本文件是流程图 Skill 与调用方之间的唯一字段合同。故事与内部规划材料见[故事切片与拓扑展开](story-planning.md)，图形与恢复规则见[图形合同](graph-contract.md)和[验收与局部恢复](acceptance.md)；本文件只声明输入、输出和写入边界。

## 接口规则

- 初次生成读取正式项目身份、`游戏企划`、`角色描述`、`场景描述`和`道具描述`。
- 正式输出是可立即展示、编辑和保存的路线对象，不依赖任何节点剧本。
- 节点、边、选择和结局均由本 Skill 生产；调用方不得用剧本补丁反向覆盖这些事实。
- 角色、场景和道具只使用上游正式名称或已登记别名，不输出资产工程 ID。
- 哈希、验收时间和路线状态是交接字段；规划草稿、复检记录和修复过程是内部数据，不进入正式输出。
- 用户所说的“集数/剧情节点数”只统计非选择的剧情内容卡；选择卡独立统计。只有用户明确说总卡数包含选择卡时，才额外锁定`nodes`总数。
- 内部检查失败只影响机器检查结论，不阻断业务交接。按恢复规则完成实际内容核对及字段组装后继续现有保存流程，不伪造内部通过回执。

## Skill 输入字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `manifest.json` | object | 是 | 正式或测试项目身份；提供当前唯一`project_id`（平台manifest可取identity.story_id）及本轮可读资产范围；身份用于实际保存，内部故事冻结不要求先绑定，缺失可独立补绑。测试时可由调用方依据用户输入构造，但不得冒充已有线上项目。 |
| `游戏企划` | object | 是 | 包含标题、目标、冲突、世界观、体量、完整故事和结局方向；节点数量建议不作为固定约束。 |
| `角色描述` | list<object> | 是 | 至少包含主角及路线必需角色。 |
| `场景描述` | list<object> | 是 | 无正式场景时允许为空列表。 |
| `道具描述` | list<object> | 是 | 无关键道具时允许为空列表。 |
| `用户要求` | string | 否 | 本轮用户逐字要求；优先于企划软建议和默认复杂度。用户自身要求冲突、故事与用户期望不匹配或缺少用户独占信息时询问，按用户明确意见继续。 |

## Skill 输出字段

```text
路线对象 object
├─ contract_version string
├─ capability_id string
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
│  └─ {edge_id: string, source_node_id: string, target_node_id: string, edge_type: "choice" | "default"}
├─ choices list<object>
│  └─ {source_node_id: string, 选项编号: string, 选项文字: string, 目标分集编号: string}
└─ endings list<object>
   └─ {node_id: string, ending_type: "main" | "expected" | "failure" | "small"}
```

## 输出约束

- 以上字段为正式交接对象的完整字段集，候选与内部草稿不能作为已验收输出交给调用方。
- `route_version`是路线内容修订标识；`contract_version`是工程协议标识，均不是 Skill 发布版本。Skill 发布版本只在 Git、留底目录和目录外发布说明维护，不写入运行说明、脚本输出、路线标识或业务内容；协议与绑定字段只交工程消费，不展示给玩家。普通 Skill 或脚本维护不修改这些协议标识，不新增发布版本一致性门禁；有效性根据实际字段、内容哈希和当前快照判断。已有路线恢复保留其身份，不因维护而重编号或换身份。
- 全部节点为兼容合同标记`node_type="episode"`；选择卡由`互动节点.是否为分支节点`和`是否有选择问题`同为`true`识别，不计入集数。结局属于非选择剧集，计入集数。
- 剧集`单集梗概`逐字取已完成故事切片，选择卡材料仅含问题，不承载独立剧情；状态填有依据的事实，资产使用实际出现的正式名称，不能编造状态。

- `contract_version`固定为`nextplay.episode-route-handoff.v1`，`capability_id`固定为`episode-route-planner-biz`。
- `route_status`必须为`accepted`；节点从`episode-001`开始连续编号，且只有一个入口。
- 图必须可达、无环并最终抵达结局；边、选择和结局索引必须与节点内事实完全一致。
- 有选择的节点至少提供两个不同目标；普通节点只有一个默认后继；结局节点后继为空且默认后继为`无`。
- `ending_type`只允许`main`、`expected`、`failure`和`small`；非结局为`null`。真结局映射`main`，不新增平台枚举；默认类型与图形要求见图形合同，用户明确要求优先。
- `route_material`必须足以支持下游写作，并明确当前节点的状态变化、资产白名单和`stop_boundary`。
- 输出不得包含完整剧本、创作分析、对白、冷读、质量结论或占位正文。

## 九字段兼容投影

- 路线独占写入`分集编号`、`分集标题`、`分集剧本.单集梗概`、`剧本分析.本集冲突`、`剧本分析.前置节点编号列表`、`剧本分析.后续节点编号列表`、`是否结局`和`互动节点`。
- `分集剧本.完整剧本`及正文实际出现的`关联角色`、`关联场景`、`关联道具`由分集剧情 Skill 写入。
- 分集剧情 Skill 可以读取路线字段，但不得修改；调用方组合两个正式产物时不得产生第二套拓扑事实源。

## 工程交接与完成边界

`route_plan.py`从已冻结故事和正式图确定性派生节点、边、选择、结局与材料，不由调用方另写一套拓扑。完成图形与投影检查后，作者审读实际各条来路的因果、选择和回汇；图形通过不代表故事审读通过。优先用`route_plan.py accept CACHE_ROOT FORMAL_ROUTE.json`派生交接对象；内部脚本失败时按恢复规则直接整理相同字段的对象交调用方，不要求内部回执或口令。`route_status="accepted"`表示作者确认本次交接内容，不能据此声称机器检查已通过。

上述路线对象是 Skill 交接合同，不是平台项目 route 文件的直接替代品。调用方按现有适配及写入网关完成九字段投影、平台节点与边映射、保存校验、并发控制和写后读回，再交 UI 展示。不得把内部 brief、主线切片文件、图形报告或规划回执直接写入平台业务字段。工程 ID 由现有适配层维护，不把临时规划 ID 当作已有画布稳定 ID。

用户只要求停在规划验收时，执行`route_plan.py accept CACHE_ROOT`，不写项目。要求路线保存展示时完成交接后停止，不自动生成完整剧本、图片或视频。失败按验收与局部恢复规则处理，保留冻结主线和已通过部分，不退回旧的规划或验收脚本。

## 已有画布输入与单集交接

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| 当前画布 | object | 是 | 完整读取的当前平台路线及 revision；以当前节点和有效连接为准。 |
| 用户要求 | string | 是 | 本轮检查、修改或生成目标；用户删除已经是决定。 |
| 目标节点 | string | 单集生成时 | 从当前集号或唯一标题解析的稳定 node_ref，不重新编号已有节点。 |
| 编辑确认记录 | object | 绑定材料时 | 对本批删改的真实处理选择及修复后读回指纹；暂停时停止相关处理。 |
| 当前节点材料 | object | 绑定材料时 | 与 route_material 同字段，仅使用当前节点、有效前情和资产文字。 |

删改交互遵守[当前画布与用户编辑](current-canvas-editing.md)，材料准备和命令遵守[当前单集材料绑定](canvas-writing-contract.md)。选择“接顺现有剧情／补写新的过渡／暂不处理”，不默认恢复旧图，不过滤错误节点绕过基础校验。

`writing-route.json`是传给编剧的当前材料快照；`canvas-writing-receipt.json`只记录授权范围、当前画布指纹及材料绑定。这里的 accepted 仅指当前材料冻结，不是新一轮 PLANNING_ACCEPTED。不得用写作快照替换平台画布、回写上游正式哈希或覆盖旧规划回执。保存目标剧本前再次核对当前画布，按当前 revision 写入目标补丁，保留其他节点、连接和媒体。
