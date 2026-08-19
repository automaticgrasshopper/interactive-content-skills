# 当前画布稳定身份门禁

本卡只在用户对现有节点新增、生成、修改、删除、移动、重连，或以“第N集”等当前位置描述目标时读取。

## 身份与位置

- `node_ref`是节点稳定身份。删除、插入、移动或自动重排后不得修改，也不得由本Skill生成。
- `display_number`、`display_id`、`display_name`只表示最新route中的当前位置，由interactive-film-game / NextPlay统一计算。
- 用户的位置说法必须先通过最新route的display字段唯一解析为`node_ref`；解析完成后立即锁定`node_ref`，后续操作不再使用display字段定位。
- 禁止根据旧分集编号、`node_ref`数字后缀、历史对话或结构变化前的位置推断当前节点。

## 全图重读

1. 收到局部操作后废弃旧快照，重新读取用户请求之后最新`project_revision`、全部节点和全部边；分页必须读完。
2. 把当前route白名单投影为`canvas-current-snapshot.json`。不得自行重编号、补写或修改任何display字段与`node_ref`。
3. 把用户每个位置定位词记录到`selections`，分别标为`target`或`anchor`，并填入从当前display字段唯一解析出的`node_ref`。
4. 运行`validate_canvas_snapshot.py`。只有当前display序号完整连续、边对称、每个定位词唯一命中其声明的`node_ref`时才生成PASS回执。
5. 回执中的`locked_node_ref`与`locked_anchor_node_refs`是后续创作的唯一节点定位输入。`resolution_audit`只留作本轮解析证据，不进入活跃创作上下文。
6. 删除、插入、移动或重连改变route后，若还有新的位置型请求，必须重新拉取最新revision并重新解析；旧回执不得跨revision使用。

## 快照合同

`canvas-current-snapshot.json`根字段：

- `contract_version`：`nextplay.canvas-current-snapshot.v2`。
- `scope`：固定`full-graph`。
- `project_revision`、`user_request_sha256`、`node_count`。
- `operation`：`add`、`generate`、`update`、`delete`、`move`或`reconnect`。
- `selections`：数组；每项严格含`selector`、`purpose`和`node_ref`。`selector`保留用户当前位置说法，`purpose`为`target`或`anchor`。
- `nodes`：全图数组；每项严格含`node_ref`、`display_number`、`display_id`、`display_name`、`predecessors`、`successors`和`choices`。边和选项目标全部使用稳定`node_ref`。

`display_number`必须是从1到当前节点总数的连续正整数。`display_id`必须唯一；`display_name`可以重复，但用它定位时必须在当前route唯一命中。

## 门禁命令

```bash
python3 scripts/validate_canvas_snapshot.py canvas-current-snapshot.json user-request.md --receipt canvas-scan-receipt.json
```

PASS后才读取`local-node-editing.md`。Skill不生成display字段，不把`node_ref`或display字段加入正式九字段结果。
