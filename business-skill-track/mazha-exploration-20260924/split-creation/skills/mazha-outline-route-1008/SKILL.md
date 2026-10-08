---
name: mazha-outline-route-1008
description: "创作或修改影游的大纲、故事与流程图：题材调研、情绪脊、剧情节点、选择后果和文字资产；支持全自动、专家分批与当前路线局部修复。正式剧本交给 mazha-screenplay-1008。"
---

# 大纲与流程图

先识别当前项目、用户范围、模式和停点，用户手改高于旧计划。项目读写使用当前绑定 `nextplay-cli`；Skill 配置保存于 Maxwell，项目路线、选择和正文实际保存到后端并读回，按[CLI 与持久化](references/cli-handoff.md)，只改变前端不算完成。

未被询问时不主动展示自动估算的体量或视频分钟数，也不让估算限制拓扑；用户明确数量和范围仍遵守。实际时长字段按[题材与提案](references/creative-entry.md)，完整图按[图形规则](references/graph-contract.md)。

## 创作与连续衔接

1. **提案与大纲**：读[题材与提案](references/creative-entry.md)，实际搜索、创作、保存读回。产品指定大纲确认时停在这里，不写路线或剧本。
2. **故事与分支方向**：确认后读[故事整理](references/story-development.md)与[情绪脊](references/emotional-spine.md)，写通确定结果的短故事，再按真实因果找岔点。仅专家首批读[六种开场](references/expert-opening.md)，首批外仍由情绪脊续接。
3. **当前事件与路线**：按[模式和范围](references/modes.md)、[连续事件与切口](references/story-planning.md)、[图形规则](references/graph-contract.md)处理当前单元。每次设计节点先读[旧目标兑现与新目标接管](references/goal-handoff.md)。保存当前剧情材料、稳定节点与边，选择及全部即时后果入口一起提交；随事件补[文字资产](references/assets.md)，不先灌满整图。
4. **交给独立编剧，再继续路线**：按[同运行交接](references/skill-handoff.md)，加载 `mazha-screenplay-1008` 为当前已保存的剧情节点写作、修订并读回正文。这里不执行底稿、增强复写或冷读工序；编剧不替这里改图。完成当前单元后，按授权继续下一段或结束本批。
5. **验收和续接**：按[路线与批次验收](references/acceptance.md)及[真实保存节奏](references/live-creation.md)核对持久化内容。全自动推进整作；专家只完成本批，按前端停点交还编辑，不把路线准备好或编剧单节点完成当本批结束。

用户仅要大纲／路线时只做该范围，不自动写剧本；仅要改剧本则直接交给独立编剧，涉及新事件或连接才先处理路线材料。按需读[画布局部修改](references/current-canvas-editing.md)、[循环／调查](references/loops.md)及[交互与真实进展](references/interaction.md)。画风、音色和媒体仍遵从用户及已选生成能力，不凭拆分扩大权限。
