# 当前画布状态门禁

本卡只在用户已经在画布上新增、删除、移动、重连节点，或指定现有节点号要求生成、修改、理顺内容时读取。

## 核心原则

将“定位范围”与“创作范围”分开：

- 定位阶段必须重新读取当前项目的全部节点和全部连线，不得使用本轮用户画布操作之前的快照、路线文件、对话记忆或节点数推测位置。
- 创作阶段才收窄到用户授权节点和必要接缝，不得顺带改其他路线。

## 必须执行的全图重读

1. 收到画布变更或节点号编辑请求后，立即废弃所有旧项目快照。
2. 调用当前平台的项目读取能力，在用户请求之后重新获取项目revision、全部节点、节点显示号、标题、全部入边、出边和选项目标。分页或分批接口必须读到结束，不得只读可见画布区域。
3. 将该次返回原样整理为`canvas-current-snapshot.json`，使用平台返回的不透明`node_ref`和`project_revision`，不自行臆造。
4. 用户指定“第23节点”时，通过当前快照的`display_id`唯一解析；用户指定标题时，只有当前快照中唯一命中才可放行。
5. 新增、生成或修改节点时，记录唯一目标节点及其全部直接前驱、后继。删除后理顺时，以当前图新形成的直接相邻节点为接缝锚点；不得继续使用被删节点的事实。
6. 运行`validate_canvas_snapshot.py`生成`canvas-scan-receipt.json`。未PASS、目标不唯一、边不对称、节点数不一致、revision缺失或用户请求哈希不匹配时，禁止生成梗概、剧本或任何写回。

## 快照格式

`canvas-current-snapshot.json`根字段：

- `contract_version`：固定为`nextplay.canvas-current-snapshot.v1`。
- `scope`：固定为`full-graph`。
- `project_revision`：平台本次重读返回的revision。
- `user_request_sha256`：当前`user-request.md`的原始字节SHA-256。
- `node_count`：平台返回的当前节点总数。
- `operation`：`add`、`generate`、`update`、`delete`或`reconnect`。
- `target_selector`：用户使用的定位词，如`23`或唯一标题。
- `target_node_refs`：新增、生成、修改时必须只有一个；已删节点可为空。
- `anchor_node_refs`：删除或重连后要理顺的当前接缝节点。
- `nodes`：全图节点数组。每项严格含`node_ref`、`display_id`、`title`、`predecessors`、`successors`和`choices`；`choices`每项含`text`与`target_ref`。

## 门禁命令

```bash
python3 scripts/validate_canvas_snapshot.py <canvas-current-snapshot.json> <user-request.md> --receipt <canvas-scan-receipt.json>
```

PASS后才读取`local-node-editing.md`的具体编辑规则。后续创作必须使用回执中的目标前驱和后继，不得再从旧对话猜测位置。
