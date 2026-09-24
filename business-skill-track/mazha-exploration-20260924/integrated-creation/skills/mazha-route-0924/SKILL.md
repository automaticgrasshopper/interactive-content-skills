---
name: mazha-route-0924
description: "影游创作：从题材调研、创意提案到故事、互动路线与剧本，随剧情补齐人物场景道具；支持全自动完成、专家分批续写及局部修改。"
---

# 影游创作

先识别当前项目、用户要求、创作模式和停点。用户已写及手改内容优先；已有作品从当前事实续接。项目读写使用 `nextplay-cli`，先读其入口与相关命令，不直接改项目 JSON。

## 一条创作链

1. **创意入口**：读[题材与提案](references/creative-entry.md)，实际搜索后给简短、有人物行动和选择可能性的提案；支持手改、再创意。指定确认停点时保存后等待，不抢跑。
2. **故事与方向**：确认后读[故事整理](references/story-development.md)与[情绪脊](references/emotional-spine.md)，写通短故事；主角的目标、事件因果与情绪变化决定岔点。
3. **边长路线边写戏**：按[创作模式](references/modes.md)确定全作或本批范围；读[拓扑展开](references/story-planning.md)、[图形规则](references/graph-contract.md)。每段先写通事件，再建节点、选择与后果，随写随补[文字资产](references/assets.md)，按[单集写作](references/screenwriting.md)完成短底稿→增强复写→冷读→保存。全自动持续执行到全部完成；专家完成本批后交还决定权。
4. **完成或续写**：按[验收与修复](references/acceptance.md)核对真实内容及读回；遵守[交互与进度](references/interaction.md)。用户打断立即停；“再做几个节点”从当前末端续长。

按需读取[当前画布修改](references/current-canvas-editing.md)与[CLI 交接](references/cli-handoff.md)；用户明确要回环或维护已有循环才读[循环／调查](references/loops.md)。机器查图形与格式，作者查因果、情绪、回汇与可拍性，不能互相冒充。画风、音色、图片和视频留到文字创作后按用户要求处理。
