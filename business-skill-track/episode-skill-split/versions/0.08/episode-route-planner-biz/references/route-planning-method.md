# 情绪脊分支图规范

1. 只从用户明确要求和用户端可见标题、一句话、大纲正文、故事体量、角色、场景、道具建立创作简报。故事体量是完稿比较信号；只有用户明确固定N集时才成为硬数量合同。

`user-intent-lock.json`中的`hard_counts`只包含`episode_count`、`choice_node_count`和`ending_count`。只从本轮用户原话抽取硬数量：用户说“N集”“N个节点”或“N个剧情节点”都写入`episode_count`，表示非选择节点的正式剧情卡总数；只有明确说“N个选择点”或“N个分支点”才写入`choice_node_count`。选择节点不计入`episode_count`，选项是边，不计入任何节点数。上游大纲自动建议、故事体量换算、助手自己陈述、`node_count_hint`及隐藏结构字段中的数量不得写入`hard_counts`。用户原话明确给出的数量写整数，未明确的一律写`null`。最终规划门禁只把非`null`项投影回正式候选图做等值核对；不核对人物、场景或道具数量，不自动改图，也不在失败后自动重试。

用户原话足以唯一确定选择、派生和结局连接时，另写`shape_mode: "exact"`及`locked_shape`；合成`start`只表示入口，不计入剧情节点数。`exact`只生成一版内容，跳过第二版、匿名比较及内容复检，最终机械门禁核对完整形状、硬数量和正式路线合同后直接保存。只有数量或局部连接不足以唯一确定全图时，不得冒充`exact`。

2. 先写一篇从开场连续到结局的单路线完整故事，补足欲望、触发事件、行动、阻力、反馈、调整、发现、关系变化、危机、高潮和结算。不得写节点、选择、拓扑或分支可能性。
3. 按自然戏剧运动把冻结故事原文连续、无重叠、无遗漏切成纯直线主线。每段建立处境、完成行动变化并形成决定或结果；不得按字数或节点预算均分。
4. 从主线已发生事件提取压力、欲望、现实反差、控制权变化和未结任务；同时依据事实与情绪运动扫描真实决定裂缝。主线原行动保留为一个选项，其他互斥可执行动作才生成第一层支线。
5. 为每个动作先写不同的即时后果和持续差异，再判断核心目标是否仍可达、人物是否仍在故事主要承诺内、情绪任务是否完成。未结束的新路线继续扫描自身事实与情绪任务中的真实裂缝，因此支线可以再次开支线，并可短于、等于或长于主线；重新面对同一可执行问题且有共同事实时才带差异回汇；永久离开核心故事时形成小结局。
6. 用户未固定结局数时，主结局是冻结完整故事自然终点；期望结局是另一条最充分兑现核心目标与题材期待的路线；失败结局必须在核心故事内推进到主要验证后失败；小结局是未走完核心故事便永久离场。用户固定结局数时，在该数量内优先兑现用户指定结局；没有逐项指定时才从这些合法类型中选择最贴合故事的组合，不为凑齐类型增加结局。
7. 从冻结故事、主线、情绪运动和支线事实生成第一版完整拓扑；不读取第一版，重新生成图形指纹不同的第二版完整拓扑。改名、换编号或改文案不算结构不同。第二版落盘后立即运行比较包命令；脚本先做图形指纹门禁，指纹相同则只重做第二版结构，尚不得生成比较包、进入匿名比较或继续后续复检。指纹不同后才匿名呈现，只比较一次：“在同样忠实于故事和情绪脊的前提下，哪一版明显拥有更丰富、自然且持续生效的互动变化，同时没有明显注水？”有明显胜者时选择胜者；没有明显差距时选择第二版。比较后才废弃落选版，不打分、不计数、不生成第三版。
8. 全图长成后按稳定广度优先顺序统一分配`episode-NNN`。汇合节点必须在全部直接前置之后；所有节点可达、无环且可抵达结局。
9. 对同一封闭材料串行完成两遍完整复检：A侧重故事投影、决定因果、即时后果、持续差异和回汇基础；B侧重结局结构、戏剧单位必要性和是否被固定形状挤压。用户未固定结局数时，B同时检查四类结局；用户固定时检查冻结数量与指定语义。两遍都必须覆盖全图。
10. 最后冻结所有节点梗概、冲突、连接、选择、结局、路线状态和停止边界。选择节点停在互斥动作成立但尚未执行处；选择首个后果由目标节点演出；结局节点完整结算。

## 私有规划证据

沿用已验证的逐文件顺序：

```text
user-request.md → user-intent-lock.json → creative-brief.json
→ complete-story.json
→ mainline-decomposition.json → mainline-emotional-movement.json
→ decision-fissure-audit.json → story-treatment.json
→ topology-draft-1.json → topology-draft-2.json
→ topology-comparison-packet.json → topology-comparison-verdict.json
→ topology-selection.json → route-candidate.json
→ topology-review-packet.json → topology-review-a.json → topology-review-b.json
→ emotional-spine.json → planning-acceptance.json
```

完整故事、决定裂缝和支线事实不再各自产生只用于留痕的独立复检文件；它们由正式候选上的A/B两遍全图复检统一覆盖。情绪脊生成后也不再追加一遍重复的材料复检，直接进入机器总验收。这样保留因果与结构质量判断，但不为没有新增判断对象的中间材料重复调用模型。

首次进入本轮缓存以及每个安全提交点都运行`workflow_state.py`，只执行它返回的唯一动作。后续文件提前存在、跳步、先写正式图再补证据、或用临时脚本组装拓扑，均使本轮缓存无效。

生成两版后运行`python3 scripts/topology_selection.py packet CACHE_ROOT --output CACHE_ROOT/topology-comparison-packet.json`。该命令先验证两版完整合法且图形指纹不同；若拒绝，不得进入比较，只允许覆盖重做`topology-draft-2.json`后再次运行一次。比较者只能读取通过门禁的匿名包，不得读取文件名映射、生成顺序或其他规划材料；输出`topology-comparison-verdict.json`后运行`python3 scripts/topology_selection.py seal CACHE_ROOT CACHE_ROOT/topology-comparison-verdict.json`。只有`TOPOLOGY_SELECTED`才可运行`python3 scripts/topology_selection.py materialize CACHE_ROOT`，并以`SELECTED_TOPOLOGY_MATERIALIZED`生成唯一正式候选。

正式路线验收前必须用`planning_gate.py create CACHE_ROOT`重新读取并绑定当前候选路线，证明完整故事、连续主线切分、拓扑前情绪运动、主线初始决定裂缝、支线事实登记中的全部正式选择、两版独立拓扑、匿名选择、节点级情绪脊以及A/B双复检均为当前版本。`decision-fissure-audit.json`只约束位于冻结主线的初始裂缝；`story-treatment.json`沿用`choice_id`、`dramatic_cause`、`question`、`options`和`merge_or_ending`，其中选项沿用`option_id`、`option_text`、`immediate_consequence`和`lasting_difference`，负责主线及递归支线的全部正式选择。不得把`mainline_node_ids`当作全图分支源白名单。每个未结束选项必须登记不同的即时后果、持续差异及后续消费节点；多条继续路线回汇时必须登记共同事实。缺少当前有效`PLANNING_ACCEPTED`时不得运行路线正式保存。

节点级情绪状态只诊断已经冻结的事件，不得倒推或修饰拓扑。类型表达只能调整已有场面的动作、反应、台词方向和后果强度，不新增节点、选择、结局、规则或资产。
