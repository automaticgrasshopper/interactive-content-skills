# 一次一个节点的完整编剧工序

继承 `episode-screenwriter-biz-format-test` 的四步，不用一句“写可拍剧本”替代。只为剧情节点写剧本，选择卡无正文。每集可以随拓扑批次落地，不要求全作已完成；目标节点自身、前情、现存选择与停止边界必须准备好。

## 1. 冻结本集事实

读当前目标、实际入边和真实前驱正文结尾；前驱为选择卡时追溯其上游剧情结尾并附该条选项原文，不伪造选择卡剧本、不混合互斥前情。普通前情未写先完成已授权的上游；循环入口同时记录首次进入和回返的事实，按 loops.md 解决写作依赖，不能等待永远未写的未来结尾。

只把本集梗概、冲突、入口事实、结果变化、停止边界、选项及当前允许资产放入写作包。人物有公开身份、身份锚与当前相关性，场景道具有公开说明。viewer_mode 根据真实入口／来路判断，不看“01”或标题。复写者不读全图、后续剧本和旧验收结论。

需要新资产先按 assets.md 补齐。内部绑定及脚本输入见 writing-context.md；这些是创作快照，不是平台路线文件，不依赖另一只编剧 Skill 或全作验收状态。

## 2. 短行动底稿

只读写作包与 compact-action-draft.md。写最短完整因果链与真正改变局面的戏剧拍，不润色、不加解释轮次，不设字数／对白配额。读回检查因果、首集理解、分支准备、停止位置。

`python3 scripts/validate_compact_draft.py node-writing-packet.txt compact-draft.md compact-draft-receipt.json`

## 3. 增强完整复写

`python3 scripts/build_enhancer_input.py node-writing-packet.txt compact-draft.md compact-draft-receipt.json enhancer-input.txt`

唯一正式写作者只读这个输入，执行 full-scene-enhancer.md 与 dialogue-and-quality.md。保留事实和戏剧拍，表达完全重写；对白以交流段为单位自然整理，不增加轮次补证明。输出 enhanced-screenplay.md；固定场次、对白、单换行格式，详见 full-scene-enhancer.md。

## 4. 冷读、检查与保存

只读写作包、增强稿、node-screenwriting.md；通过或指出现有段落问题并整稿退回。退回后从同一冻结输入完整复写，不逐条贴补；材料本身有缺口则回协调层，只改受影响事实并重建包。

通过后组装单节点内部补丁，正文逐字等于增强稿，检查证据只引已有最小片段，不为验收加戏：

`python3 scripts/accept_node_screenplay.py writing-route.json node-context.json node-writing-packet.txt compact-draft.md compact-draft-receipt.json enhancer-input.txt enhanced-screenplay.md node-draft.json node-patch.json`

脚本检查输入绑定、事实范围、阶段衔接和格式，不证明文采与因果。脚本故障依 acceptance.md 诊断，不绕过真实格式／连续性缺陷，不伪造通过。由 CLI script set/edit 写真实目标正文与 mentions，再读回。保存前目标／入边／资产变了就废弃旧包重读，不能凭旧 revision 强写。

只有保存读回才是本集完成；一集失败不回滚其他集。用户只改字按其范围直接更新，不强迫重写全剧；涉及事件或连接时先协调事实再重写相关节点。内部草稿、证据、hash 和分析不得写进正式正文或聊天回复。
