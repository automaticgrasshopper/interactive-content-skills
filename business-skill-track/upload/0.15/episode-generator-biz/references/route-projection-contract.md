# Nextplay 路线投影合同

本合同只负责把已通过全部业务门禁的十一字段`分集列表`确定性投影为Nextplay路线，不改变创作、情绪脊、剧本、选择或结局。

## 唯一事实源

- 业务 JSON 是唯一事实源；投影器不得重新推导节点、选择、连线或结局。
- `route.data.nodes`同时含剧情节点与选择节点，并按网页实际显示顺序统一使用连续的`episode-xxx`作为`node_ref`和`episode_ref`。业务互动节点原编号保存在`metadata.business_episode_ref`；业务选择编号保存在`metadata.choice_ref`与`interaction.interaction_ref`。
- 业务 JSON 中的选择仍只封装在来源分集一次；路线投影层据此确定性生成唯一独立`choice-xxx`节点，不增加分集对象。
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
- 数组第一项、`entry_node_ref`和唯一入度为0的节点都固定为非空剧情`episode-001`，三者不一致立即失败。
- `metadata.is_ending`直接使用boolean `是否结局`。
- 所有`video`节点固定`interaction.has_interaction=false`，不得直接承载问题、选项或选择边引用。
- 有选择时，剧情节点用一条`default`边连接紧随其后的唯一独立`node_type=choice`选择节点；该节点仍使用已冻结的连续`episode_ref`，固定`interaction.has_interaction=true`，填写唯一业务选择编号、问题和选择边引用，每个选项从该节点生成一条`choice`边。
- `choice`节点的`content.script.text`与`interaction.after_plot_beat`必须非空；网页必须先呈现该剧情信息，再呈现问题和选项。禁止把选择节点投影为空壳。
- 目标节点的`episode_ref`在投影阶段一次确定，网页不得从选择目标重新编号。
- 无选择时，剧情节点直接用`default`边连接后续剧情节点。
- 结局节点不得有出边；非结局节点不得成为死路。

正确可视顺序是：

```text
episode-001视频剧情节点 → choice-001独立选择节点 → 目标episode视频剧情节点
```

禁止：

```text
首个choice节点 → episode-001
把episode-001自身改成choice-001而丢失剧情卡
用`node_type=video`伪装选择节点
清空choice节点的content.script.text或after_plot_beat
从选择目标重新生成显示序号
episode-001视频节点直接承载选择信息
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

- route视频剧情节点数＝`E`
- route独立选择节点数＝`C`
- route节点总数＝页面预计可视节点总数＝`E + C`
- `slot:episode`数量＝`E`
- 路线不得包含工程合同未声明的`settings`
- 首个可视节点＝非空剧情`episode-001`

任一不等式成立都必须失败，不得提交。
