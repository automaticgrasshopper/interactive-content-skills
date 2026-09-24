# 内部写作快照与平台边界

现有六个编剧脚本保留本集不可变输入、底稿绑定、完整复写输入和原子验收；它们只读写线程创作缓存，不访问平台、不承担保存。旧 capability_id 只是脚本兼容枚举，不代表调用另一个 Skill。

协调者从当前 CLI 读回构造 writing-route.json：contract_version=`nextplay.episode-route-handoff.v1`，capability_id=`episode-route-planner-biz`，真实 project_id、当前 route_id／route_version、nodes。本集快照 route_status=`accepted` 仅表示当前材料已核对，不能作为整部拓扑已完成或平台已保存的证据。不要把它覆盖平台 route 文件。

每个相关节点含真实 node_id、当前标题、route_material、前置节点编号列表、后续节点编号列表、是否结局、ending_type、互动节点及 node_route_material_hash。route_material 含单集梗概、本集冲突、entry_state、state_changes、allowed_characters、allowed_scenes、allowed_props、stop_boundary；事实来自当前正文与实际连线，不伪造状态。互动节点保存当前选择问题、选项、真实目标、默认后继；无选择则显式为空。

内部 `互动节点` 的精确字段如下，不能用 question/options 等自造别名：

```json
{"是否为分支节点":true,"是否有选择问题":true,"选择问题":"先查哪里？","选项列表":[{"选项编号":"实际 option_id 甲","选项文字":"查看柜台","目标分集编号":"实际目标甲"},{"选项编号":"实际 option_id 乙","选项文字":"去找哥哥","目标分集编号":"实际目标乙"}],"默认下一分集编号":"无"}
```

平台将选择卡独立保存时，写作快照必须把紧接目标剧情的真实选择卡问题及选项投影到这个**上游剧情的只读互动材料**，才能检查本场是否已准备好每个行动。选择卡本身仍无剧本，真实拓扑不改变，不把投影对象写回平台。无选择的本集填 false/false/空问题/空选项及真实默认后继（没有则“无”）。普通单后继不代表没有选择准备：先查看后继是否正是选择卡。保存前重新读回检查这一映射。

使用 scripts/screenplay_contract.py 的 node_hash、route_hash 对实际快照计算绑定，不编造 hash。node-context.json 的字段与 stage_contract.py 完全一致：

- contract_version=`nextplay.episode-screenwriting-context.v1`
- project_id、route_id、route_version、route_output_hash、node_id、node_route_material_hash
- characters[]：name、public_identity、identity_anchor、current_relevance，允许 relationship_context、speech_profile
- scenes[]、props[]：name、public_description
- direct_predecessor_endings[]：node_id、ending_excerpt；按当前直接前驱逐条绑定，选择卡附其真实上游结尾及所选动作，不编选择卡正文。

`python3 scripts/build_node_writing_packet.py writing-route.json node-context.json NODE_ID node-writing-packet.txt`

无人物或场景基础事实时先由协调者补材料，不猜权限。循环的返回前驱初次尚无剧本时只用已核对的返回事件原文并明确“回返事件材料，非已保存剧本”；等本循环各集完成再核对真实返回正文，必要时重建包。首入与回返分别说明，公共节点不能依赖互斥前情。不冒充已存正文。

node-draft.json 沿用 screenplay_contract.py 的 PATCH_FIELDS：contract_version、capability_id、project_id、route_id、route_version、route_output_hash、node_id、node_route_material_hash、screenplay、screenplay_hash、status、accepted_at。contract_version=`nextplay.episode-node-patch.v1`，capability_id=`episode-screenwriter-biz`；验收脚本 seal 计算真实输出字段。

screenplay 包含分集剧本（只有完整剧本）、剧本创作分析（创作分析、场景和段落展开计划、连续性分析、冷读与质量问题、验收结论）、关联角色／场景／道具、派生信息、quality_checks。检查涵盖 route_fidelity、stop_boundary、continuity、first_appearance、spatial_continuity、prose_dramatization、asset_consistency；有对白加 dialogue，分支来源加 choice_readiness，具体以脚本真实 REQUIRED_CHECKS 及条件检查为准。证据逐字取正文，不为凑证据加戏。

只有正文与实际资产 mentions 进入 CLI script 保存；这些内部分析与旧九字段投影不写进平台。脚本无法运行按 acceptance.md 人工核对同等内容并保留失败记录，不能产生假回执。
