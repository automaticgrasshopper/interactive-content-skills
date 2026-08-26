# 情绪脊分支图规范

1. 只从用户明确要求和用户端可见标题、一句话、大纲正文、故事体量、角色、场景、道具建立创作简报。故事体量是完稿比较信号；只有用户明确固定N集时才成为硬数量合同。
2. 先写一篇从开场连续到结局的单路线完整故事，补足欲望、触发事件、行动、阻力、反馈、调整、发现、关系变化、危机、高潮和结算。不得写节点、选择、拓扑或分支可能性。
3. 按自然戏剧运动把冻结故事原文连续、无重叠、无遗漏切成纯直线主线。每段建立处境、完成行动变化并形成决定或结果；不得按字数或节点预算均分。
4. 从主线已发生事件提取压力、欲望、现实反差、控制权变化和未结任务；同时依据事实与情绪运动扫描真实决定裂缝。主线原行动保留为一个选项，其他互斥可执行动作才生成第一层支线。
5. 为每个动作先写不同的即时后果和持续差异，再判断核心目标是否仍可达、人物是否仍在故事主要承诺内、情绪任务是否完成。未结束的新路线继续扫描自身事实与情绪任务中的真实裂缝，因此支线可以再次开支线，并可短于、等于或长于主线；重新面对同一可执行问题且有共同事实时才带差异回汇；永久离开核心故事时形成小结局。
6. 主结局是冻结完整故事自然终点；期望结局是另一条最充分兑现核心目标与题材期待的路线；失败结局必须在核心故事内推进到主要验证后失败；小结局是未走完核心故事便永久离场。
7. 从冻结故事、主线、情绪运动和支线事实生成第一版完整拓扑并废弃；不读取第一版，重新生成图形指纹不同的正式拓扑。改名、换编号或改文案不算结构不同。
8. 全图长成后按稳定广度优先顺序统一分配`episode-NNN`。汇合节点必须在全部直接前置之后；所有节点可达、无环且可抵达结局。
9. 对同一封闭材料串行完成两遍完整复检：A侧重故事投影、决定因果、即时后果、持续差异和回汇基础；B侧重四类结局、戏剧单位必要性和是否被固定形状挤压。两遍都必须覆盖全图。
10. 最后冻结所有节点梗概、冲突、连接、选择、结局、路线状态和停止边界。选择节点停在互斥动作成立但尚未执行处；选择首个后果由目标节点演出；结局节点完整结算。

## 私有规划证据

沿用已验证的逐文件顺序：

```text
user-request.md → user-intent-lock.json → creative-brief.json
→ complete-story.json → complete-story-review.json
→ mainline-decomposition.json → mainline-emotional-movement.json
→ decision-fissure-audit.json → decision-fissure-review.json
→ story-treatment.json → story-treatment-review.json
→ topology-draft-1.json（立即废弃）→ route-candidate.json
→ topology-review-packet.json → topology-review-a.json → topology-review-b.json
→ emotional-spine.json → route-material-review.json → planning-acceptance.json
```

首次进入本轮缓存以及每个安全提交点都运行`workflow_state.py`，只执行它返回的唯一动作。后续文件提前存在、跳步、先写正式图再补证据、或用临时脚本组装拓扑，均使本轮缓存无效。

正式路线验收前必须用`planning_gate.py create CACHE_ROOT`重新读取并绑定当前候选路线，证明完整故事、连续主线切分、拓扑前情绪运动、主线初始决定裂缝、支线事实登记中的全部正式选择、第一版拓扑、节点级情绪脊以及A/B双复检均为当前版本。`decision-fissure-audit.json`只约束位于冻结主线的初始裂缝；`story-treatment.json`沿用`choice_id`、`dramatic_cause`、`question`、`options`和`merge_or_ending`，其中选项沿用`option_id`、`option_text`、`immediate_consequence`和`lasting_difference`，负责主线及递归支线的全部正式选择。不得把`mainline_node_ids`当作全图分支源白名单。每个未结束选项必须登记不同的即时后果、持续差异及后续消费节点；多条继续路线回汇时必须登记共同事实。缺少当前有效`PLANNING_ACCEPTED`时不得运行路线正式保存。

节点级情绪状态只诊断已经冻结的事件，不得倒推或修饰拓扑。类型表达只能调整已有场面的动作、反应、台词方向和后果强度，不新增节点、选择、结局、规则或资产。
