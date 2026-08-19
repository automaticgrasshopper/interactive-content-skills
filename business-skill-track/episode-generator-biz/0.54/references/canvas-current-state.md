# 当前画布稳定身份门禁

本卡只在用户对现有节点新增、生成、修改、删除、移动、重连，或以“第N集”等当前位置描述目标时读取。

## 身份与位置

- `node_ref`是节点稳定身份。删除、插入、移动或自动重排后不得修改，也不得由本Skill生成。
- `display_number`、`display_id`、`display_name`只表示最新route中的当前位置，由interactive-film-game / NextPlay统一计算。
- “第N集”和纯数字只匹配`node_type=video`的`display_number`；`display_id`或`display_name`按最新route精确匹配。解析完成后立即锁定`node_ref`，后续不再使用display字段定位。
- 禁止根据旧分集编号、`node_ref`数字后缀、历史对话或结构变化前的位置推断当前节点。

## 本轮重读与刷新

1. 每次局部请求都只接受调用方本轮提供的完整当前route；它无条件覆盖旧route、旧快照和旧定位回执。业务Skill不读取NextPlay路径、project revision、工程哈希或并发状态。
2. 把本轮route白名单投影为`canvas-current-snapshot.json`。不得自行重编号、补写或修改`node_ref`与任何display字段。
3. 把用户每个位置定位词记录到`selections`，分别标为`target`或`anchor`。唯一解析成功时写入对应`node_ref`；未命中或不唯一时写`null`。
4. 运行`validate_canvas_snapshot.py`。当前输入无法唯一定位时，脚本必须返回`REFRESH_ROUTE_REQUIRED`；立即交还调用方重新读取一次当前完整route，期间不得AskUser，也不得声称节点不存在。
5. 重读后重新建立快照并再运行一次。只有PASS回执中的`locked_node_ref`与`locked_anchor_node_refs`可以进入局部创作。
6. 第二次仍未命中或不唯一时，才可根据当前候选中性AskUser；不得使用旧编号、旧快照或旧回执补猜。

## 快照合同

`canvas-current-snapshot.json`根字段：

- `contract_version`：`nextplay.canvas-current-snapshot.v3`。
- `scope`：固定`full-graph`。
- `user_request_sha256`、`node_count`。
- `operation`：`add`、`generate`、`update`、`delete`、`move`或`reconnect`。
- `selections`：数组；每项严格含`selector`、`purpose`和`node_ref`。`selector`保留用户当前位置说法，`purpose`为`target`或`anchor`，首次未解析时`node_ref`为`null`。
- `nodes`：全图数组；每项严格含`node_ref`、`node_type`、`display_number`、`display_id`、`display_name`、`predecessors`、`successors`和`choices`。边和选项目标全部使用稳定`node_ref`。

`node_type`为`video`或`choice`；两类`display_number`分别从1连续排列。`display_id`全图唯一；名称定位必须在当前route唯一命中。

## 门禁命令

```bash
python3 scripts/validate_canvas_snapshot.py canvas-current-snapshot.json user-request.md --receipt canvas-scan-receipt.json
```

PASS后才读取`local-node-editing.md`。Skill不生成display字段，不把`node_ref`或display字段加入正式九字段结果。
