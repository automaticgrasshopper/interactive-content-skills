# 当前单集材料绑定

已有画布的写作输入由流程图Skill准备，编剧的写法、冷读、正文验收和单节点补丁不变。这里验收的是当前用户确认后的写作材料，不是新路线全图规划；无需修改编剧Skill、平台或预设。

## 输入与命令

CURRENT_ROUTE是刚完整读取的nextplay.route.v1。STATE是canvas_writing.observe/confirm产生的本项目编辑确认记录。先按current-canvas-editing完成真实用户确认与所选接缝修复，通过现有网关完整保存并读回，再为唯一目标准备MATERIAL.json，字段与route_material相同：单集梗概、本集冲突、entry_state、state_changes、allowed_characters、allowed_scenes、allowed_props、stop_boundary。

所有材料来自当前剧集、当前有效连接和现有公开资产文字，不读取旧formal-route覆盖当前梗概。允许从当前企划/文字资产提取本集实际出现的人物和场景，不猜新机制；缺少必需事实时询问。当前梗概只有尾部旧选择提示失效时，在派生材料中局部校准；不能提前替玩家选一个结果。状态只传当前确有依据的内容，未冻结则为空对象，不从断开分支继承独占经历。MATERIAL不写回画布。

```bash
python3 scripts/canvas_writing.py build CURRENT_ROUTE.json STATE.json NODE_REF MATERIAL.json OUT_DIR
```

程序核对项目、当前基础图形合法、修复后确认指纹、目标存在且为剧集，以真实边投影现存节点、连接、有效选项和目标材料，写出：
- writing-route.json：兼容nextplay.episode-route-handoff.v1的当前材料快照，route_version以canvas-write开头；accepted仅指本次材料冻结，不是PLANNING_ACCEPTED。
- canvas-writing-receipt.json：单集授权范围、当前画布指纹、revision、目标材料绑定及写作快照哈希。

不会改CURRENT_ROUTE、旧规划回执或其他正式文件。不会补节点、接边、重编号稳定ID、把无出边剧集标为结局。当前图有无目标的边、不可达剧集、少于两个方向的选择卡或环时拒绝构造写作材料，返回具体问题交由上述三种方式处理，不能过滤掉错误后继续。不得把本集正文中的旧二选一当成当前事实。

## 交接与读回

将writing-route.json作为本次正式路线材料传给现有编剧Skill，按其接口构造同一快照绑定的NODE_CONTEXT；重建plan-index而不是复用旧索引。context中的实际前情只取当前有效前驱；遇选择卡取其现存进入方向及选项事实，不虚构选择卡剧本。缺失真实前情正文时遵循编剧接口澄清必要资料，不批量生成未请求的剧集。

保存前重新完整读取CURRENT_ROUTE并运行：

```bash
python3 scripts/canvas_writing.py verify CURRENT_ROUTE.json OUT_DIR
```

若画布内容/连接变了，旧材料作废，重读并确认新批次；只有媒体、排版或其他剧本变化时不要求重新选择处理方式。目标剧本保存仍用当前revision做CAS，不能拿旧revision强写。补丁的绑定对应writing-route，调用方把已验收正文投影到当前目标剧本字段，保留当前节点、边和媒体，不将writing-route替换正式画布。

此模式不运行旧缓存的route_plan.accept。要求当前全部节点从入口可达、选择方向有效、无悬空与环，并通过现有网关；不重新强加初次生成的复杂度配额。正式生成新路线仍走原完整强校验。
