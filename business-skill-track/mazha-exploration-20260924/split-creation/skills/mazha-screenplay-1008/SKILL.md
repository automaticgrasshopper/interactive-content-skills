---
name: mazha-screenplay-1008
description: "把已保存影游节点的上游资料，经同类型写法调研与自然语言剧情，直接写成正式剧本并逐段保存；支持已有剧本的局部修改。不创作大纲、不重建流程图，不走短底稿、增强复写或写作验收流程。"
---

# 从剧情直接写剧本

按用户确定的顺序：**取得上游资料 → 联网搜索同类型题材怎么写 → 结合现有信息与目标转移套路，用自然语言讲出本集剧情 → 直接写正式剧本 → 实际保存读回。** 不另做短底稿、增强复写、冷读、写作包或验证回执。

先使用当前 `nextplay-cli` 读回真实项目、当前节点、实际入边与前驱正文、已保存大纲和相关资产，用户手改优先；选择卡无剧本。每次写自然语言剧情和正文都按[实际体验视角](references/scene-writing.md#实际体验视角)继承最新 `settings.perspective/player`，第一人称落实为角色眼中的现场，不只换代词。沿用上游主副标签，合计最多 5 个，调整交回大纲 Skill 保存同步。读[题材写法与自然剧情](references/genre-research-and-treatment.md)，结合整句意图确认人物、昵称和疑似网络梗，未查清时优先补搜抖音、B 站；清楚就做，普通名字不硬凑梗，明显歧义简短问清。新恋爱或联动不要求已有 CP，不因没搜到现成关系而洗成同名原创人物。保留实际身份与特征，实际调研后给自然语言剧情。每次设计这段剧情和开始写正文都读[旧目标兑现与新目标接管](references/scene-writing.md#旧目标兑现与新目标接管)，不靠无关新任务硬转场。

自然剧情确定后按[直接编剧](references/screenwriting.md)与[场景写作](references/scene-writing.md)直接写正式正文，对白按[对白写法](references/dialogue.md)。已经写出的完整行动段按[逐段保存](references/live-creation.md)写入同一节点当前累计正文；写完、实际保存并读回一致才算本集完成。项目保存遵从[CLI 工程与持久化](references/cli-handoff.md)，不把自然剧情或前端变化当后端正文。

在同 Agent、同 Thread、同 Run 中接收协调者从 `mazha-outline-route-1008` 逐段方法或 `nextplay-route-planning` 完整拓扑交来的已保存节点任务；单节点写完交回协调继续本批，不提前发整批 final、AskUser 或解锁编辑。用户直接要一个已有节点或局部台词时按其范围处理，不为改字重搜题材或扩全剧。

新的自然剧情需要改变既定事件、来源、选择或连接时回路线 Skill 局部修材料并保存，再继续正文。必要文字资产按[随剧情补资产](references/assets.md)保存真实 ref，增强人物细节不发明新权限／规则。循环只跟随实际路线，按[已有循环](references/loops.md)处理。只改受影响正文，保留稳定 ID、媒体和无关手改；中断后从当前后端接续。拆分不额外授权图片、视频或发布。

共享 CLI 的 screenplay 参考只用于真实 context、字段、成品格式与保存接口；本 Skill 覆盖其中五阶段、行动底稿、冷读、台词复写和失败整稿重来流程。`script inspect --include context` 的 episode.summary 是实际上游故事切片，保留事件、停止边界和全部合法来路；不能要求同事 planner 提供私有写作包。涉及改图按活跃规划 generate edit/rewrite-segment、完成规划普通 route edit 分派，不越权重启全图。
