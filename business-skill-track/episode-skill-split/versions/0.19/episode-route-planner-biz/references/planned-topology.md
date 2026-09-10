# 正式拓扑与投影合同

先用 `topology-exploration.md` 简短比较可能的因果组织，明确废弃草图的损失与正式方案的理由；不必写全图或满足正式数量。此文件不作任何下游事实源，不入回执。

正式提交 PLAN.json：

```json
{"expected_topology_hash":null,"reason":"首次正式规划","plan":{"nodes":[],"edges":[]}}
```

每个 nodes 对象：

```json
{"node_id":"n1","kind":"scene","title":"当前节点标题","route_material":{"单集梗概":"该节点的事件骨架：人物处境、实际行动、直接后果与停止位置。","本集冲突":"当前可演的具体冲突与阻力。","entry_state":{},"state_changes":{},"allowed_characters":[],"allowed_scenes":[],"allowed_props":[],"stop_boundary":"本节点停止于已发生的明确时刻。"},"ending_type":null,"emotional_movement_ids":["m1"],"mainline_segment_id":"s1"}
```

kind为scene/choice/ending。choice增加 `question` 与 `options:["动作一","动作二"]`；主线动作标记可用mainline_option_index。ending须将ending_type设为main/expected/failure/small。支线mainline_segment_id为null。全部切片恰好映射一个节点，主线路径依次直接相连，从入口到结局。主线原文已经执行的动作只能放到选择后继，不强求选择梗概逐字等于包含后果的原切片。

边为 `{source_node_id:"n1",target_node_id:"n2",option_index:null}`。选择每个选项恰好一条边，option_index为零基整数；普通节点恰好一条边且index为null；结局无出边。允许指向尚未排列到的节点，第一节点必须是唯一入口。无需按创建顺序限制汇点。

状态使用稳定事实键，entry_state是节点所需前提，state_changes是在本节点实际造成的赋值。无需重复未变字段，脚本沿每条路径继承其余事实。回汇可用 `{"证据来源":{"one_of":["录音","目击"]}}` 表达共同任务接受两种来源；不能把one_of当作未来随机赋值。初始事实在简报initial_state，分支独有事实必须在实际获取节点的state_changes建立。entry_state为空表示没有额外前提，不等于无视真实前提；语义复检必须发现漏记。未列出的事实保持，不自动清空；更改关系、消耗资源须有事件证据。

```bash
python3 scripts/topology_plan.py freeze CACHE_ROOT PLAN.json
python3 scripts/topology_plan.py ledger CACHE_ROOT
python3 scripts/planned_gate.py packet CACHE_ROOT
```

freeze验证结构、完整主线与用户硬数量，写topology-state.json修订链；作者不得手改此状态。ledger枚举所有入口至结局路径并逐路径检查状态前提，保留不同出口状态；不能截断路径表冒充全部。脚本统一分配episode-001等ID，route-ledger.json的node_id_map提供临时ID映射。

A/B通过后写 `episode-synopses.json`：

```json
{"topology_hash":"freeze返回的当前哈希","nodes":[{"node_id":"episode-001","单集梗概":"只投影对应冻结事件，不增添选择、动作或结局。","本集冲突":"该节点可演出的具体冲突。","stop_boundary":"选择节点明确停在所有选项都尚未执行的位置。"}]}
```

必须恰好覆盖全体正式节点，不能包含任何边、状态、选项或资产字段。运行 `topology_plan.py materialize CACHE_ROOT` 生成候选，不能手改候选。选择当前处境与后继选项后果分别审查。

局部改图时读取status，复制当前plan，只修受影响节点/边，保留所有无关临时ID与事实；提交当前expected_topology_hash与具体reason再次freeze。旧图保留在revisions，下游自动归档失效；重新记账、A/B、梗概投影与最终验收。上游八项在首个freeze后不可回写；若其本身错误，明确报告失效文件与受影响范围，不删除历史冒充续跑。
