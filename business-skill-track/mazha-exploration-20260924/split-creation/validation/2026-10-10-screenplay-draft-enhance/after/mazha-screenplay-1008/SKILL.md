---
name: mazha-screenplay-1008
description: "为已保存影游节点编写或修改剧本：调研同类写法，讲通并保存本集梗概，写短底稿，再增强复写为正式场景并逐段保存。支持局部修改；不创作大纲、不重建流程图，不另设冷读或写作验收。"
---

# 从剧情、短底稿到正式剧本

按用户确定的顺序：**取得上游资料 → 调研同类型写法 → 讲通并保存本集梗概 → 短底稿 → 增强完整复写 → 正式正文逐段保存读回。** 短底稿搭好戏，增强复写把同一组变化充分演出来；不另设冷读、台词复写或写作验收阶段。

先使用当前 `nextplay-cli` 读回真实项目、当前节点、实际入边与前驱正文、已保存大纲和相关资产，用户手改优先；选择卡无剧本。每次写自然语言剧情和正文都按[实际体验视角](references/scene-writing.md#实际体验视角)继承最新 `settings.perspective/player`，第一人称落实为角色眼中的现场，不只换代词。沿用上游主副标签，合计最多 5 个，调整交回大纲 Skill 保存同步。读[题材写法与自然剧情](references/genre-research-and-treatment.md)，结合整句意图确认人物、昵称和疑似网络梗，未查清时优先补搜抖音、B 站；清楚就做，普通名字不硬凑梗，明显歧义简短问清。新恋爱或联动不要求已有 CP，不因没搜到现成关系而洗成同名原创人物。保留实际身份与特征，实际调研后给自然语言剧情。每次设计这段剧情和开始写正文都读[旧目标兑现与新目标接管](references/scene-writing.md#旧目标兑现与新目标接管)，不靠无关新任务硬转场。

按[编剧工序](references/screenwriting.md)先将本集自然剧情保存到真实节点 summary，在节点梗概正文区展示；再按[短底稿](references/compact-action-draft.md)冻结行动、反馈和变化，最后按[增强完整复写](references/full-scene-enhancer.md)写正式场景。底稿和增强输入只留当前 Thread 工作区，不覆盖梗概或正式剧本。增强阶段读取[场景写作](references/scene-writing.md)和[对白写法与口语实例](references/dialogue.md)，正文的完整行动段按[逐段保存](references/live-creation.md)写入同一节点当前累计 text；写完、实际保存并读回一致才算本集完成。项目保存遵从[CLI 工程与持久化](references/cli-handoff.md)。

在同 Agent、同 Thread、同 Run 中接收协调者从 `mazha-outline-route-1008` 的逐段、完整 CLI 或增量方法交来的已保存节点任务；单节点写完交回协调继续本批，不提前发整批 final、AskUser 或解锁编辑。用户直接要一个已有节点或局部台词时按其范围处理，不为改字重搜题材或扩全剧。

新的自然剧情需要改变既定事件、来源、选择或连接时回路线 Skill 局部修材料并保存，再继续正文。必要文字资产按[随剧情补资产](references/assets.md)保存真实 ref，增强人物细节不发明新权限／规则。循环只跟随实际路线，按[已有循环](references/loops.md)处理。只改受影响正文，保留稳定 ID、媒体和无关手改；中断后从当前后端接续。拆分不额外授权媒体；但本轮 ui.simultaneous_images=true 已授权当前开头/本批实际用到的人物、场景与道具形象生成时，协调者须加载自己的 mazha-asset-image-direct-1008 真实生图、保存读回并逐图确认后再移交，不能以只做开头为由省略。false 时人物、场景与道具均不自动生图，独立一键拓扑仍不顺带媒体。

共享 CLI 的 screenplay 参考只用于真实 context、字段、成品格式与保存接口；本 Skill 采用自己的短底稿与增强复写两阶段，覆盖共享文档的五阶段、冷读、台词复写和失败整稿重来流程。`script inspect --include context` 的 episode.summary 是实际上游故事切片，保留事件、停止边界和全部合法来路；不能要求完整 CLI 方法 提供私有写作包。涉及改图按活跃规划 generate edit/rewrite-segment、完成规划普通 route edit 分派，不越权重启全图。
## 本轮范围与展示

先核对本轮创作计划、用户原话和真实节点。只导入已有故事或路线且用户未要求写剧本时，不启动编剧；已有剧本导入/复用用 canvas，格式整理用 progress，不假装重新创作，不为展示预写未来节点。本轮实际新写或实质整理节点梗概时，将 route create/revise 任务标为 write，targets 使用 node:真实node.id，本轮全部目标可用空数组；正式剧本新写/实质修订另用 script write 和 script:同一真实node.id。沿用实验 SP 的创作计划与阶段协议，不为内部底稿新增产品任务或界面；本集梗概只由真实节点 summary 驱动原位打字，既有【本集剧情】标记仅兼容解析，不作为独立界面或保存证明。无创作计划的明确写作请求仍按用户范围执行。局部改字不强制重搜或扩写全剧；实际需要新写法时才按下文调研，相关已读来源可复用。

