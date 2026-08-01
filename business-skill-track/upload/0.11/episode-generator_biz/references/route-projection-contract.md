# Nextplay 路线投影合同

本合同只负责把已通过全部业务门禁的十一字段`分集列表`确定性投影为Nextplay路线，不改变创作、情绪脊、剧本、选择或结局。

## 唯一事实源

- 业务 JSON 是唯一事实源；投影器不得重新推导节点、选择、连线或结局。
- `route.data.nodes`只含剧情节点，数量、编号和顺序必须与`分集列表`完全一致。
- 选择不是`route.data.nodes`中的独立节点。它由来源剧情节点的`interaction`对象和同源`choice`边共同表达一次。
- `slot:episode_router`和全部`slot:episode`必须来自同一份业务 JSON 与同一份已验证路线，不得混用旧缓存或临时结构。

## Boolean 规则

以下字段只能是JSON原生boolean：

- `是否结局`
- `选择节点.是否为选择节点`
- `选择节点.是否有选择问题`
- `互动节点.是否为互动节点`
- `互动节点.后边是否接选择节点`

禁止把它们与`"是"`、`"否"`、`"true"`或`"false"`比较。类型不是boolean时立即失败，不做容错转换。

## 投影规则

对每个分集对象创建且只创建一个`video`剧情节点：

- `node_ref`和`episode_ref`均等于`分集编号`。
- `content.script.text`逐字使用`完整剧本`，不得用梗概、选择问题或结果替代。
- `entry_node_ref`固定为`episode-001`。
- `metadata.is_ending`直接使用boolean `是否结局`。
- 有选择时，`interaction.has_interaction=true`，填写唯一选择编号、问题和选择边引用；每个选项生成一条`choice`边。
- 无选择时，`interaction.has_interaction=false`，后续使用`default`边。
- 结局节点不得有出边；非结局节点不得成为死路。

正确可视顺序是：

```text
episode-001剧情卡 → choice-001选择卡 → 目标episode剧情卡
```

禁止：

```text
choice-001 → episode-001
episode-001内选择 + 独立choice-001重复投影
```

## 固定命令

只运行Skill内置脚本，不临时重写：

```text
python3 scripts/build_route_projection.py BUSINESS_JSON BASE_ROUTE_JSON ASSETS_JSON PROPOSED_ROUTE_JSON --outline-revision N --assets-revision A --asset-catalog ASSET_CATALOG --expected-endings E --expected-formal F --expected-failure X
python3 scripts/validate_route_projection.py BUSINESS_JSON PROPOSED_ROUTE_JSON
```

合并路线后，必须对合并后的`route.json`再运行一次`validate_route_projection.py`。提案与合并后结果都通过，才允许发出最终槽位。

## 数量不变量

设：

- `E`＝`分集列表`长度
- `C`＝`是否有选择问题=true`的唯一分集数量

则：

- route剧情节点数＝`E`
- route唯一选择数＝`C`
- 页面预计可视节点总数＝`E + C`
- `slot:episode`数量＝`E`
- 首个可视节点＝非空剧情`episode-001`

任一不等式成立都必须失败，不得提交。
