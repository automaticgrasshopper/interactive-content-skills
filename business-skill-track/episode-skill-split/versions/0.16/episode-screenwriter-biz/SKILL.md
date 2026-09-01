---
name: episode-screenwriter-biz
description: "当且仅当已有由流程图 Skill 正式保存并验收的互动路线，用户要求为其中一个指定节点生成、预览、修改、检查或验收正式分集剧情、场景、对白和完整剧本，或在正式剧本完成后的继续对话中形成改名、正文修改或新的完整剧本时使用本 Skill。一次只处理一个node_id；路线不存在、未验收或绑定失效时停止，不自行规划、重建或改写拓扑。"
---

# 分集剧情编剧

## 用户可见进度

开始前读取`references/user-visible-progress.md`。内部文件名、字段、标识、合同、哈希、脚本、回执、补丁、门禁和推理过程只供机器执行，不得显示给用户，也不得进入正式剧本。每个阶段只在真正开始时播报对应的一句自然语言。

## 冻结输入

正式路线是只读依赖。一次只接收一个`node_id`，并同时绑定`project_id`、`route_id`、`route_version`、`route_output_hash`和`node_route_material_hash`。上游已经冻结的事实触发、人物理解、人或关系变化及后续行为影响必须服从；上游未单独冻结这些字段时，不等于人物只能执行无情感的事实过桥，可以从当前事件、人物基础、当前关系和直接前情中推导本场动机与关系质感，但不得借此改写路线、提前演出未来节点或登记正文没有真正造成的持久变化。此外必须收到按`references/business-interface.md`绑定的`单节点写作上下文`，其中包含当前允许人物的公开身份与当前相关性、允许场景和道具的公开说明，以及全部直接前情正文结尾；前情已有正式状态快照时一并提供。

路线不存在、`route_status`不是`accepted`、合同版本不支持、任一绑定不一致、节点不存在、白名单内容不完整或首次人物只有姓名没有公开身份时，立即返回明确依赖错误。不得自行重建路线、改写梗概、修正拓扑或猜测人物职业、权限和资产机制。

## 不可修改

不得修改或提交节点ID、节点类型、标题、父子关系、边、选择数量、选择文案、选择目标、默认后继、结局布尔值、结局类型、路线状态事实、允许资产或停止边界。输出只能是对应`node_id`的`episode-node-patch`，不得提交整个路线。

## 成稿后的对话追改

目标节点已有正式剧本后，若用户在继续对话中要求改名、修改正文，或对话已经形成新的完整剧本，读取`references/post-acceptance-revision.md`。该模式只允许额外读取当前已验收剧本和本轮可见对话，不得读取被废弃的旧稿；把已经明确采用的修改并入本轮写作目标后，仍以现有冷读和原子验收保存新的正式节点补丁。讨论中的备选不落盘；聊天中已经形成最新版而正式产物仍是旧版时，不得报告完成。

## 四步单节点写作链

### 一、冻结写作包

同一路线首次写作前，把全图已有梗概、冲突、入口状态、状态变化和连接整理成一次性`episode-plan-index.json`。该索引不新增剧情、不做第二次情感规划，也不把规划证据或复检结论交给写作者；路线哈希未变时直接复用。

```bash
python3 scripts/build_episode_plan_index.py FORMAL_ROUTE.json episode-plan-index.json
```

按`references/business-interface.md`验证正式路线、`单节点写作上下文`与指定节点，生成唯一`node-writing-packet.txt`。写作包只投影整集图形位置、直接后续计划和各后继方向最近的已有情感转折；这些内容只帮助当前节点建立基线或铺垫，不得复述，也不得提前演出。前序补丁的验收证据和完整旧稿不进入写作包，只传实际变化压成的当前行为状态。`viewer_mode=entry|continuation`只根据目标节点有没有前置节点派生；不使用节点ID、标题或显示顺序判断第一集。

```bash
python3 scripts/build_node_writing_packet.py FORMAL_ROUTE.json NODE_CONTEXT.json NODE_ID node-writing-packet.txt --plan-index episode-plan-index.json
```

### 二、行动底稿

进入本阶段时向用户播报`正在撰写初稿`。

只读取写作包与`references/compact-action-draft.md`，写`compact-draft.md`。本阶段只决定这场戏有哪些真正改变局面的戏剧拍，以及它们的情感因果顺序和停止位置；已有冻结双因果时逐项承接，没有时只从现有材料推导本场成立的动机与关系表达。企划、人物关系或当前路线明确包含恋爱主线或事业线中的恋爱体验时，额外读取`references/romance-scene-realization.md`；其他项目不得调用。入口节点同时决定观众理解所需事实由哪个现有戏剧拍承载，但不另造背景说明拍，也不负责正式人物介绍、空间调度、成品对白或语言风格。

```bash
python3 scripts/validate_compact_draft.py node-writing-packet.txt compact-draft.md compact-draft-receipt.json
```

### 三、完整增强复写

进入本阶段时向用户播报`正在进行润色`。

底稿通过后生成唯一 Enhancer 输入。Enhancer只读取该输入，依据`references/full-scene-enhancer.md`负责整场表达，并只在写对白时使用`references/dialogue-and-quality.md`；它是唯一正式剧本写作者，不保留底稿原句的义务。它只能表达底稿已有戏剧拍，不增加证明轮次、解释轮次或装饰性调度。

```bash
python3 scripts/build_enhancer_input.py node-writing-packet.txt compact-draft.md compact-draft-receipt.json enhancer-input.txt
```

增强稿写入`enhanced-screenplay.md`。若冷读发现问题，废弃本次增强稿并从同一冻结输入重新完整复写，不在成品上零碎贴补第三版。

### 四、冷读与原子验收

开始冷读时向用户播报`正在对照细节`。冷读只读取冻结写作包、正式剧本与`references/node-screenwriting.md`，只作通过或整稿退回判断，不参与写作、不逐项补证据。全部内容检查通过、开始组装正式正文时播报`正在完成终稿`；开始把通过检查的正文写入当前分集结果时播报`正在合并剧本`。阶段失败不得提前播报后一阶段。

冷读通过后组装现有节点草稿合同，其中`分集剧本.完整剧本`必须逐字等于`enhanced-screenplay.md`；质量证据只能引用正文已经自然存在的最小片段，不能为了凑检查项扩写正文。随后运行：

```bash
python3 scripts/accept_node_screenplay.py FORMAL_ROUTE.json NODE_CONTEXT.json node-writing-packet.txt compact-draft.md compact-draft-receipt.json enhancer-input.txt enhanced-screenplay.md NODE_DRAFT.json NODE_PATCH.json --plan-index episode-plan-index.json
```

只有标准输出出现独立一行`NODE_SCREENPLAY_ACCEPTED`才保存该节点补丁。验收同时把正文实际形成的人物变化、定向关系变化和可供后续调用的共同记忆写入`派生信息`，再合并为不含证据原句的当前状态快照；下一节点只读取该快照。任一阶段哈希失效、正式正文不等于增强稿或质量证据不足时失败，不写输出，不影响正式路线、其他节点或已验收节点。

上述标准输出和错误只供机器判断。对用户只按`references/user-visible-progress.md`显示自然语言；保存成功后显示`本集剧本已完成`。

## 批量与预览

预览就是只处理用户指定的一个节点。调用方以后可逐次传入多个节点，但每个节点必须独立读取、生成、提交、验收和保存；禁止临时批处理脚本，禁止一个节点失败回滚其他节点。

## 停止边界

正文必须停在当前`stop_boundary`内。选项动作属于边，选项造成的首个可见后果属于目标节点；当前节点不得提前演出后续独占核验、选择或结果。
