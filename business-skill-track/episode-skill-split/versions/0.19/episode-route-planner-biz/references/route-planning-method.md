# 故事与分支规划

冻结输入依次为以下八项；前七项沿用 0.18 数据合同，新增支线事实登记。正式编号只由拓扑脚本分配。

1. `user-request.md`：用户原话，不能混入测试报告要求或推断数量。
2. `user-intent-lock.json`：`{hard_counts:{episode_count,choice_node_count,ending_count,total_node_count},shape_mode:"open"|"exact"}`，未指定数值为 null；用 `python3 scripts/user_constraints.py CACHE_ROOT/user-request.md` 原样提取。仅用户唯一确定连接才为 exact 并附 locked_shape，数量锁不是形状锁。可另记题材、必保和禁区。
3. `creative-brief.json`：`{project_id,title,characters:[],scenes:[],props:[],initial_state:{}}`，数组为允许名称，可附冲突、关系、题材承诺。initial_state只登记开场之前已成立的共享事实，未发生的线索或好感不得提前注入。测试身份须明确为独立测试；可由上游按自然输入构造，不冒充线上已有项目。
4. `complete-story.json`：`{contract_version:"nextplay.episode-complete-story.v1",title,complete_story}`。写成一篇从开场到自然结局的连续故事，欲望—行动—阻力—反馈—关系变化—结算完整；不预制分集、空树或所有支线。恋爱题材须兑现个人情感目标，悬疑须有信息链，用户指定的新题材元素应与主要承诺共同成立。
5. `mainline-decomposition.json`：`{mainline_segments:[{segment_id,source_text}]}`。按自然戏剧单位连续、无遗漏、无重叠切原文。裂缝在切片内部时继续在原文边界拆分：来源切片结束于决定已成立而动作尚未执行，动作在下一切片。须在冻结前完成这次修正。
6. `mainline-emotional-movement.json`：`{emotional_movements:[{movement_id,segment_ids,pressure,desired_state,reality_shift,control_change,unresolved_task,candidate_fissures}]}`。所有切片至少被一个运动覆盖；candidate_fissures为数组，其余事实项为非空文字。
7. `decision-fissure-audit.json`：`{decision_fissures:[{fissure_id,source_segment_id,emotional_movement_ids,decision_question,actions:[{option_id,option_text}]}]}`。必须在人物当时资源、知识和动机下可执行且互斥；主线行动保留为一个选项。无自然选择或用户禁用选择时为空数组。
8. `story-treatment.json`：`{choices:[{choice_id,source_fissure_id,dramatic_cause,question,options:[{option_id,option_text,immediate_consequence,lasting_difference}],continuation}],endings:[{title,kind,unlock_chain,causal_payoff}]}`。支线新选择的source_fissure_id可为null，其原因必须源于前一步后果。先推直接后果，再推持续差异和未结任务；允许前瞻规划完整支线，但不能为了指定结局倒造无因果的中段。continuation说明再次分岔、回汇或退出的事实依据。kind为main/expected/failure/small的语义分类，不设每类最低数。

采用的每个动作在正式拓扑中都须有即时后果和持续兑现。支线走完独立冲突可以回汇，但带入不同证据、关系或代价；后续节点不能只因共用ID就假定各路径历史相同。结局因核心目标状态与未结任务是否结算而成立，不能因节点预算余量自动结束。固定数量要求在正式冻结前调配戏剧单位，保持故事本身与所有硬约束共同成立。

## 展开方向：鼓励交织，鼓励开扇

在推演支线后果与比较拓扑组织时，主动考虑以下两种方向：

- **鼓励交织**：不同人物线、目标线或调查线可以互相提供条件、施加代价；支线经过自身冲突后，带着不同知识、资源与关系进入共同任务，再按这些差异分岔。让前面的选择影响后面的可执行行动与结局，形成多次分合或跨线承接，而不只是几条互不相关的平行线。图上线条交叉本身不算交织，共用节点也不代表不同路径自动共享物证或关系成果。
- **鼓励开扇**：当处境确实提供多种行动方向时，允许一个选择打开三个或更多有意义的选项，也允许各条支线在遇到新冲突后继续展开。给每个方向独立的戏剧空间、后果和去向，不默认二选一、短支线或立刻回主线。选项多少由角色当时可做的事决定，不用同义选项或无因果死路凑宽度。

两者可以结合：先开扇、跨线交织、带差异回汇，再展开新的方向；也可以只采用其中一种。用户锁定的数量、连接、无分支要求和故事因果优先，不设最低扇出、交织次数或额外评分门禁。正式图必须真实表达每条边的可执行条件，不能只在文字里承诺隐藏门槛。
