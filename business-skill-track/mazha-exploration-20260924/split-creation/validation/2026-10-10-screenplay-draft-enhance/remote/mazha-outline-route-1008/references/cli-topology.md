# CLI 完整拓扑方法

以下方法复制自用户指定的共享拓扑 Skill，作为本“大纲与流程图”Skill 的完整规划参考，原版资源不改。调用前先按 [当前作品续拓扑交接](continuation-handoff.md) 读当前项目并确定工程状态：空图或可续做的活跃 route generate 才走下文完整流程；已 done 或无规划的非空图走该参考的普通 route edit 增量路径，不执行新 start/replace-route，也不为套这份流程重建已有图。

前文大纲规则、玩家实际视角、明确数量与本轮范围优先；AI 自动体量按 creative-entry.md 处理。图专项不自动写正式剧本；既有剧本、用户手改、删除与稳定引用保留。逐段情绪脊方法的六种开场和内部图形检查不强加到本方法。下文的规划中审读与工程检查属于 CLI 合同，不把它们变成独立编剧的额外写作验收；编剧按自己的短底稿→增强复写两阶段执行，内部材料不写进节点梗概或正式剧本。

# 互动路线规划

使用已加载的 `nextplay-cli`，首次使用按其 Skill 初始化。命令为 `nextplay.bin route generate …`，按 next 回执的 input_spec 构造输入，不预先查询 `--help`；仅回执缺格式或报错信息不足时查询；不直接修改项目 JSON 或 state.json。本流程不使用 subagent。

## 确认范围

保留用户原话，以 `start` 回执的 context_brief 读取大纲全文和资产索引，资产详情按需 inspect，不等待资产图片。开局模板：`nextplay.bin route generate start --user-request-file <用户原话文件>`。没有实质歧义就继续，不为阶段转换询问用户。任务范围以真实用户消息为准，自己的审读建议或工具提示不是新的用户要求。空路线 `start`；未完成的规划 `next` 续做；用户要求重来用 `start --new` 创建独立记录，旧画布保留到第一次 `mainline-cut --replace-route`，可先 dry-run。其他已有画布局部修改仍用普通 `route edit`。next=done 后规划结束：之后的路线修改用普通 `route edit`，不再回到 route generate（不调用 next/edit/rewrite-segment/reconcile），也不受本 Skill 的规划规则约束；用户要求重新规划时用 `start --new`。

`intent` 只记录用户明确事实、数量、必保事件、体量和结局要求。`long_story` 按用户或上游已确认的体量类别填写：确认为“短”（如总视频 10–15 分钟）时填 false；没有类别时，全部视频不足 15 分钟为短篇。长篇的默认结构是硬检查；短篇不查交织、深度等图形，但仍需小结局、期望、坏结局、真结局四类各至少一个，主要结局锁定分散。只有用户明确的数量、结局或禁止项能免除。剧情集数包含结局，选择另计；局部连接要求不推导成全图数量。上游的章节或分幕数不是全图视频数。未明确数量则省略 counts；required_checks 默认省略，只在用户明确要求对应结构时逐项填写，不把大纲的结构描述自行映射成检查项。结局数量相同不代表方向覆盖：逐项核对大纲已有和用户新增的结局，未明确总数时不自行锁定 ending_count。确有体量与必保经历冲突时说明具体取舍，记录实际答复，不编造 user_clarification。

`required_endings` / `forbidden_endings` 只接受 `small|expected|failure|main` 类型；具体结局名称、达成条件与事件放进 `must_keep`。类型错误不能通过删除故事要求解决。读取 `next.duration_requirement` 中来自开始时大纲的原文，对照真实用户要求填写 `duration.scope/min_minutes/max_minutes`；“全部视频总量”和“一条游玩路径”分别用 `all_video`、`single_path`。不能因原话在大纲而漏录；未记录时 check 会阻止完成。

## 提交、审读、选择

每次跟随 `next`。首次写故事前读 [故事与审读](cli-topology-story-and-review.md)；规划支线、全图检查前读 [支线与质量取舍](cli-topology-branches-and-quality.md)。

提交回执含独立审读建议；逐条判断，认同则 `--revise` 后看新建议，不认同直接进入下一步。与用户要求或 must_keep 冲突时以用户要求为准。建议不是用户要求，不能据此改题、`start --new` 或声称用户提出新要求。

提交下一步材料即消费上一对象；未修订就继续的建议会记为 not_adopted。同一对象一般修订不超过 2 次；仍有 high 可继续，不为 low 反复重写。审读 unavailable 或 partial（部分单元失败）时流程继续；可在对象尚未消费时以相同内容 `--revise` 重试，已成功单元使用缓存。

`story-core`、`mainline-*`、`branch-*`、`edit`、`segment-*`、`check` 可能在命令内审读，exec 设 `timeout: 300`；超时后先 `next` 查看是否已写入，不直接重复提交。超过 10 分钟的 running 会显示 interrupted。写输入文件与提交放同一次 exec（heredoc + 提交）。正文仍在上下文时无需读回，恢复上下文时按需 inspect。

## 创作顺序

1. `story-core`：优先按 continuation-handoff.md 读取提案阶段已留存的同一完整短故事并原文提交；仅缺稿时，才先想清故事主轴五问，再写一条实际经历和确定结局的完整短故事并留存；提交后按回执建议核对大纲中的显式机制、能力与证据规则，按 [故事与审读](cli-topology-story-and-review.md) 核对。
2. `mainline-story`：沿已确定短故事写连续长故事，用独占行 `<!-- cut:p1 -->` 标候选切口。构思可用抉择的问题、原动作、替代动作和开始执行原动作的第一句；切口在选项动作之前。阅读回执建议。
3. `mainline-cut`：从原文切片，按集填写冲突、停止边界、`assets`、`estimated_minutes`。`assets` 必填，列本集正文实际出场的角色、场景、道具引用（取自 context_brief），某类没有填 `[]`；branch-cut、segment-cut 同样。以正文中实际出场为准，以代称出场的也列入，只被提及而未出场的不列。一集通常 0.5–1 分钟、围绕一件主要事件，按实际演出估时；all_video 长故事的主线合计一般不超过上限一半，出现 `branch_reserve_warning` 时先拆细或缩短主线剧集。decisions 必填 action_start，逐字引用原动作首句；它必须位于 before_episode 正文开头，不能把句子改成别的事件来通过校验。非主线选项填写 landing 标题与动作要点。提交立即出现主线、选择和落点剧集；切片在提交下一步前可 --revise 调整结构，同 ID 原地更新；已消费的长故事用 rewrite-segment 修订。提交下一步后切片只作追溯，此后画布是唯一内容来源。
4. `branch-shape`：先定全图形状，再写支线正文。为每个待展开选项写段（一段是一个直接后果，通常 1–2 集）：标题、一句梗概、预计分钟和出口（新选择、回汇或结局），并写出段后的选择问题与选项。重要选择两边都要继续发展并产生下一轮决定；不利选择先产生可补救、重组或转向的新局面；两翼在不同共享事件交织后再开扇；期望结局形成阶梯。CLI 把形状投影到画布并跑结构检查，只作提示：`structure_gaps` 给出缺项的定义、骨架和最接近的候选，可修订形状或在写支线时补上；形状不验收，结构在 check/complete 对正式画布强制。形状不写画布，写正文时发现更好的结构先 `--revise` 形状。notes 可记录取舍。
5. `branch-story --from-option <选项>`：next 给出建议选项、它在形状中的计划（`planned`：段、出口及后续选择）和来路；改选其他选项或需要回汇节点开头时用 `inspect --step origin --option <选项>`。只写这个选项的直接后果，写到计划的出口为止：出口是选择时，停在主角执行动作之前，不能写成主角已经权衡并选定其一；没有后续决定时才写到结局或回汇。正文与主线一样用 `<!-- cut:b1 -->` 标记切口，首行必须是标记。不读失效长故事、不迁就落点标题；提交、阅读回执建议。一次只写一个选项：写完、看审读、认同则 `--revise`，再切片和进入下一个选项；`open_review` 提醒上一条仍有未处理建议。回执有 high/medium 建议时 `review_required` 排在最前；未修订就进入下一步会先被 `REVIEW_PENDING` 拦一次并列出建议，认同则 `--revise`，不认同再发同一命令即继续（记为不采纳）。修订后的版本不再拦；complete 对全图审读建议同样拦一次。
6. `branch-cut`：从支线正文切片，声明结局、回汇、新选择或 conditional 条件分流出口；计划的选择用 `exit.type=choice`（或 decisions），id 与选项 id 沿用形状，后续方向才能对上计划。回执的 `shape_deviation` 指出缺少计划出口，应修订正文或形状；`projected_structure` 显示按形状完成后的全图结构。提交即原地更新落点为首集，并写后续剧集及新落点。可汇入已有选择节点，不能汇入待展开落点，应先展开该方向。条件出口用 conditions 分流到已有 target 或新 landing；新落点继续 branch-story/cut，所有新结局（包括失败结局）必须经过正文创作、切片与审读，不能用 edit 新增结局。提交下一步前可修订当前对象；之后草稿只作追溯。重复支线步骤，直到无待展开选项；新选项不在形状中时先修订 branch-shape。
7. `check`：每次跑确定性检查，无 blockers 和待展开选项后内置全图审读；阅读建议后按需修改，再 check。`--no-review` 只跑确定性检查。完成前至少跑一次不带 `--no-review` 的 check（`review_note` 会提醒）。长篇缺默认结构时报 `DEFAULT_STRUCTURE` 阻止完成，`structure_gaps` 说明缺项与最接近的候选：修订形状，对已写支线用 rewrite-segment 在 segment-cut 加入新选择，或用 generate edit 的 insert-choice/connect 接回目标开头能演出该动作的已有节点，再 check。`default_gaps` 只剩超长剧集，拆开后再 check。
8. `complete`：对每个尚存退化项用 `{decisions:[{check,reason}]}` 说明接受理由；超长剧集确实不能拆时用 `{check,node_refs,reason}` 豁免。默认结构不能在这里豁免。修复后重新检查即可清除。按返回的统计、预计路径时长、结局时长及已知问题交付，不再全量 route inspect，不声称机器证明故事质量。next=done 后交付本次结果，规划到此结束。

`next` 返回下一步、input_spec 或其引用、待展开选项、建议选项的计划与来路。读回形状用 `inspect --step branch-shape`。

## 修改画布与主线保护

以下规则只适用于未完成的规划。小改用 `route generate edit`，复用普通 route edit 的 operations；直接新增结局或把本规划 edit 新增、尚无故事切片来源的节点改成结局会报 ENDING_STORY_REQUIRED。新结局使用 branch-story/cut，或对普通节点完成 segment-story/cut；已有切片结局的措辞和 ending_type 仍可修补。不得改走普通 route edit/reconcile、重开规划或直接写 JSON 绕过这条创作要求。跨集调整用 `rewrite-segment --from <节点> --to <节点>`，读取当前画布组成的起稿，再提交 `segment-story`，阅读建议后提交 `segment-cut`。沿用节点的切片必须填写 `node_ref`，不填就新建；未被引用的旧节点视为删除。结构变化列出受影响选择、支线出发点和回汇边，按错误逐项提交 boundary_operations，不隐式丢边。带剧本或媒体的待删节点会被拒绝。

已写入的主线只因主线自身剧情问题修改；支线接不上，改支线或换成立的回汇位置。`edit` / `rewrite-segment` 涉及主线必须 `--reason`，回执审读附修改理由，核对是否为了迁就支线或图形结构。

画布已写入后修订 intent 只使检查失效，不重交短故事或长故事。保留真实用户约束，不为通过检查调低要求或机械缩短估时；估时以一集 0.5–1 分钟的实际演出为参照，时长不够时先拆细剧集、压缩单集事件，不删减玩家决策；每次切片读 duration_progress：all_video 的已分配时长和余额还要容纳未展开支线；single_path 不套用全图余额。超时优先删减、合并实际剧情后重新估算；估时必须有实际演出依据。

选择节点只呈现基于已发生剧情的问题与选项，新事件、对白及选择后果由视频节点承载，不用连续的选择节点代替剧情推进。节点正文只能演出一种确定情况，不按来路分情况叙述，也不用“或”、对比句等去掉条件词后仍并列两种过去的写法。来路差异先在专属过渡节点演出，或用条件边分流到各自实际发生的节点；共享节点只写每条来路都成立的具体动作。状态计数相同不等于此前经历相同，共享结局不能借用某一条来路独有的物件、伤痕或地点。逐来路核对进入事实→当前动作→离开事实，包括时间地点和不可逆变化；关键事实应有明确来源，不成立就修到正文。

时长保存在规划节点映射中，用 `estimated_minutes` 修改；不写成 objective 的时长模板。资产按每集实际出现的人物、地点、道具绑定，不统一给所有节点绑定同一套。

规划未完成时，普通 `route edit` 和用户直接编辑属于外部修改；出现 `USER_ROUTE_EDIT_DETECTED` 时采用 next 的 route_version，通过 `reconcile` 确认当前映射，不把正文同步回旧草稿、不恢复用户删除内容。删除落点即移除待展开方向，同时处理只剩一个方向的选择。受影响内容按 next 重新检查。

## 历史与故障

`history [--plan-id <id>]` 列出已发布规划与快照，`inspect --plan-id <id> --step <材料>` 只读旧材料；不切换画布。新规划使用独立目录，旧根目录材料保留。首次替换旧画布保存五文件快照，处理旧节点所属生产对象和生成关联，保留共享资产及媒体文件；共享引用冲突按错误显式处理。

旧版流程留下的规划不再兼容，需要时用 `start --new`。`PLAN_START_PENDING` 用 `recover-start`；`partial_saved` / `WORKFLOW_WRITE_PENDING` 先检查实际 I/O 与产物，再 `recover-write`。恢复遇到后续编辑会停止，保留快照与日志；不要重建节点、改状态或新建规划绕过未完成写入。
