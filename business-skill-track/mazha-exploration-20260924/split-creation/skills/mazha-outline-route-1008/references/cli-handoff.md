# CLI 做项目工程，Skill 做创作

先加载当前绑定的 nextplay-cli 入口，按真实文档初始化一次；只在工具能力不明时读相关 help／schema。不能凭此文档猜完整命令参数或自行补 runtime.env、密钥、项目身份。

读取当前 manifest、inspect 与必要节点／资产，确认当前用户作品和实际版本。outline 保存提案，asset add/update 保存文字，当前策略的 route create/edit 或 route generate 保存节点连线，script set/edit 保存正文；使用 CLI 真实支持的路径和参数，遵守 dry-run、并发检查、校验、保存与读回。工具本身已保存读回就不再调用旧网关重复保存。

- 逐段策略的 route create 仅用于空图，返回的 reference_map 是新 client_key 到稳定引用的依据；已有图用 edit 保留稳定 ID 与媒体。
- 内部 graph_check 的 scene/choice/ending 是创作投影；平台以 CLI 实际 schema 为准。不要直接把整个内部 JSON 写进 route。
- 专家待续末端是未完成的普通剧情，不伪造 is_ending；CLI 如允许保存未连接末端，记录 warning 与续写计划，不能把本批状态说成作品可发布。若拒绝，报告具体限制，不能绕过写文件。
- script 只写剧情节点。正文中实际出现的人物、场景、道具用真实资产 ref 的 mentions；名称到 ref 映射以读回为准。编辑正文保留无关 mentions 与媒体，实际不再出现的引用同步调整。
- 一个选择单元可一起提交完整选择与后果入口，避免半个失效选择卡；随后依 live-creation.md 分别推进实际正文与资产，不批量提交整作，不等待动画。
- partial_saved／冲突先读实际结果，仅补未成功部分，不把整批重放成重复节点。工具不支持的条件、变量、动态选项不得写入自造字段。

CLI 的 PASS 证明工程合同与保存结果，不证明 woven、情绪脊、情节连贯或写作合格。反之内部创作检查不是平台权限；平台拒绝保存不能用人工验收绕过。初始化、读取和写入错误只作简短准确说明，内部命令、hash 与制作话语不进玩家剧本。

## 视角保存与继承

视角存在当前 `nextplay/current/outline.json` 的 `data.play.perspective`，统一使用 `first`（第一人称）或 `third`（第三人称）。当前 CLI 可用 `outline update --field play.perspective --value first`（第三人称用 `third`），或在真实 `outline update --input` 补丁中保存 `{"play":{"perspective":"first"}}`；然后 `outline inspect --field play.perspective` 读回。随大纲保存实际采用的推荐或玩家选择，不能只在回复、前端或临时上下文写一个名称。玩家扮演的身份记录在已有 `play.player`，明确角色与关系，不另造视角字段。命令前缀及项目绑定仍按当前 CLI 文档。

大纲确认、路线规划和续写前读最新视角；玩家在前端改选后，以后端已保存值为准，不用旧提案覆写。值缺失或旧中文值时，结合最新明确选择与实际记录，经上述接口补齐或规范化并读回；不根据空值偷偷重置已有作品。第一人称的节点和选择只使用玩家角色能看到、听到、经历或被告知的信息，不安排脱离角色的秘密旁观；第三人称允许外部观看与多线叙事，但信息何时揭露仍服从既定悬念。两种路线方法都遵守，不要求共享 planner 新增字段。

用户改视角时先保存新选择，再按授权调整受影响的节点材料和剧本，保留无关内容、稳定引用与媒体；不能只替换“我／他”。已有剧本、分镜或媒体若仍按旧视角制作，如实说明受影响范围，不把设置保存说成全部内容已重制，不自动重做图片或视频。

## 后端保存与读回

本节适用于所有创作模式及后续修改，不受专家开场形状规则的范围限制。用户修改 Skill 后要求执行新规则，或要求修改已有路线／剧本时，必须把本轮实际项目变更保存到后端项目文件。仅修改 Skill 不自动重写已有作品；Skill 配置在 Maxwell 保存并读回，只有用户授权的项目修改才写入项目数据。

路线节点、选项、连接及分集剧本保存在当前项目 `nextplay/current/route.json`。先读当前 CLI 与目标当前版本：已有图且规划已完成使用 `route edit`；活跃未完成规划按下一段处理。剧本使用 `script set/edit` 等真实支持的命令。CLI 负责校验、版本及引用维护、写盘和读回，不能直接编辑 JSON，也不能用前端状态、打印输出、缓存、内部 graph 或规划草稿冒充该文件。

修改完成必须同时满足：实际写入回执成功；从持久化项目读回的目标节点／边／剧本与本轮修改相符。可复用 CLI 回执中已经提供的实际读回证据；回执没有目标内容或不能确认时，再用 `route inspect` 或 `script inspect` 读取并比对。`dry_run` 不算保存；`unchanged` 只有当前持久化内容已经符合要求才算完成。失败、`partial_saved` 或结果不明时先查实际状态，只补未成功部分，不重复整批，不声称“已修改完成”。

CLI 保存成功只证明项目文件保存并读回，不代表远端投影或前端刷新。需要交付前端结果时，再确认页面同步；页面尚未更新要准确说明同步状态，不能只调整显示来掩盖后端未写入。保留未涉及的节点、稳定引用、媒体与用户手改内容。

## 同事规划的保存与修改

普通完整图按 nextplay-route-planning 和真实 next.input_spec 使用 route generate，切片写 summary 和稳定节点，正式 script 不提前填入。活跃未完规划的改图使用 generate edit，跨集 rewrite-segment 后提交 segment-story/cut，保留 node_ref；新结局必须经真实故事切片，不绕过 ENDING_STORY_REQUIRED。外部用户改图触发 USER_ROUTE_EDIT_DETECTED 时读 next.route_version 并 reconcile，保留当前画布和删除，不恢复旧长故事。next=done 后结束 generate，后续局部改图只用普通 route edit，不再 reconcile。partial_saved 或超时先 next／检查现状，再按合同恢复，不盲目重复创建或 start --new。
