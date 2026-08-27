---
name: episode-screenwriter-biz
description: "当且仅当已有由流程图 Skill 正式保存并验收的互动路线，用户要求为其中一个指定节点生成、预览、修改、检查或验收正式分集剧情、场景、对白和完整剧本时使用本 Skill。一次只处理一个node_id；路线不存在、未验收、版本或哈希失效时停止，不自行规划、重建或改写拓扑。"
---

# 分集剧情编剧

## 用户可见进度

开始前读取`references/user-visible-progress.md`。内部文件名、字段、标识、合同、哈希、脚本、回执、补丁、门禁和推理过程只供机器执行，不得显示给用户，也不得进入正式剧本。每个阶段只在真正开始时播报对应的一句自然语言。

## 冻结输入

正式路线是只读依赖。一次只接收一个`node_id`，并同时绑定`project_id`、`route_id`、`route_version`、`route_output_hash`和`node_route_material_hash`。此外必须收到按`references/business-interface.md`绑定的`单节点写作上下文`，其中包含当前允许人物的公开身份与当前相关性、允许场景和道具的公开说明，以及全部直接前情正文结尾。

路线不存在、`route_status`不是`accepted`、合同版本不支持、任一绑定不一致、节点不存在、白名单内容不完整或首次人物只有姓名没有公开身份时，立即返回明确依赖错误。不得自行重建路线、改写梗概、修正拓扑或猜测人物职业、权限和资产机制。

## 不可修改

不得修改或提交节点ID、节点类型、标题、父子关系、边、选择数量、选择文案、选择目标、默认后继、结局布尔值、结局类型、路线状态事实、允许资产或停止边界。输出只能是对应`node_id`的`episode-node-patch`，不得提交整个路线。

## 四步单节点写作链

### 一、冻结写作包

按`references/business-interface.md`验证正式路线、`单节点写作上下文`与指定节点，生成唯一`node-writing-packet.txt`。这一步只负责冻结不能改的事实；后续写作者不得回读全图、其他路线、旧稿或验收结论。

```bash
python3 scripts/build_node_writing_packet.py FORMAL_ROUTE.json NODE_CONTEXT.json NODE_ID node-writing-packet.txt
```

### 二、行动底稿

进入本阶段时向用户播报`正在撰写初稿`。

只读取写作包与`references/compact-action-draft.md`，写`compact-draft.md`。本阶段只决定这场戏有哪些真正改变局面的戏剧拍，以及它们的因果顺序和停止位置；不负责人物介绍、空间调度、成品对白或语言风格。

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
python3 scripts/accept_node_screenplay.py FORMAL_ROUTE.json NODE_CONTEXT.json node-writing-packet.txt compact-draft.md compact-draft-receipt.json enhancer-input.txt enhanced-screenplay.md NODE_DRAFT.json NODE_PATCH.json
```

只有标准输出出现独立一行`NODE_SCREENPLAY_ACCEPTED`才保存该节点补丁。任一阶段哈希失效、正式正文不等于增强稿或质量证据不足时失败，不写输出，不影响正式路线、其他节点或已验收节点。

上述标准输出和错误只供机器判断。对用户只按`references/user-visible-progress.md`显示自然语言；保存成功后显示`本集剧本已完成`。

## 批量与预览

预览就是只处理用户指定的一个节点。调用方以后可逐次传入多个节点，但每个节点必须独立读取、生成、提交、验收和保存；禁止临时批处理脚本，禁止一个节点失败回滚其他节点。

## 停止边界

正文必须停在当前`stop_boundary`内。选项动作属于边，选项造成的首个可见后果属于目标节点；当前节点不得提前演出后续独占核验、选择或结果。
