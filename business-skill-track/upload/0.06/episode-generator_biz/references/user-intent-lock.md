# 用户意图内部合同

本文件只约束私有运行缓存，不增加正式输入、正式输出或数据库字段。用户明确要求是创作事实来源；上游建议、Skill 默认偏好、结构启发式和模型判断不得覆盖它。

## 建立顺序

在压缩上游输入、生成情绪脊或拓扑前，先把本轮可见的用户要求原文保存为私有 `user-request.md`，再生成 `user-intent-lock.json`：

```json
{
  "contract_version": "nextplay.user-intent-lock.v1",
  "source_sha256": "<user-request.md 的 SHA-256>",
  "resolution_status": "resolved",
  "constraints": [
    {
      "constraint_id": "user-001",
      "statement": "必须保留的明确要求",
      "scope": ["global"],
      "required": true,
      "forbidden_literals": []
    }
  ],
  "conflicts": [],
  "resolutions": []
}
```

- 只登记用户明确说出的主线、关系、规则、关键事件、选择、结局、固定数量和禁改范围，不把 Skill 建议伪装成用户要求。
- `scope` 使用 `global`、`topology` 或冻结后的 `episode-xxx`；冻结前无法定位时先用 `global`，冻结后补成真实范围。
- `forbidden_literals` 只登记用户明确禁止且可以逐字检出的词句，不用关键词替代语义审核。
- 偏好可以记录，但只有 `required=true` 的约束进入完成态硬门禁。
- 合同、源文本、冲突、证据和摘要都只存在于画布外，不得进入三个公开文件、业务 JSON、进度消息或玩家界面。

## 前后意愿冲突

先判断新旧要求是否可以同时成立：

- 可以同时成立：同时保留；若新要求明确修订旧要求，把旧项记入 `resolutions` 为 `superseded`，以最新明确要求为准。
- 无法同时成立，且会改变主线、人物关系、关键事件、选择、结局或硬数量：把 `resolution_status` 设为 `needs-user`，在 `conflicts` 中写明冲突约束、一个中性问题和互斥选项，然后立即调用 AskUser。用户回答前不得生成情绪脊、拓扑或正文。
- 若运行环境没有 AskUser 工具，直接向用户提出同一个简短问题并停止；不得自行挑选，不得用“更合理”覆盖任何一边。
- 用户回答后保留解决记录，更新有效约束，将状态改回 `resolved`，重新计算合同摘要。

## 独立履约复检

所有正文和冻结拓扑完成后，独立读取 `user-request.md`、合同、拓扑和全部分集，生成私有 `user-intent-review.json`：

```json
{
  "review_version": "nextplay.user-intent-review.v1",
  "source_sha256": "<源摘要>",
  "contract_sha256": "<合同摘要>",
  "artifact_sha256": "<拓扑与全部正文摘要>",
  "constraints": [
    {
      "constraint_id": "user-001",
      "satisfied": true,
      "evidence": [
        {"location": "episode-005", "quote": "最终正文中的逐字短证据"}
      ],
      "explanation": "证据如何满足用户要求"
    }
  ],
  "issues": []
}
```

- 每个有效硬约束必须逐项覆盖；不能用空泛结论代替正文或拓扑证据。
- `quote` 必须逐字存在于指定拓扑或分集；跨集要求可以提供多条证据。
- “没有发生某事”仍需独立语义判断，并说明检查范围；脚本只额外拦截合同中明确登记的禁用字面内容。
- 任一要求不满足、证据不足或存在未解决问题时，先定点返修，再重新复检。
- 最终组装器验证源摘要、合同摘要、全部创作物摘要、逐项证据和问题清单。合同摘要也绑定逐集复检回执；用户要求变化后旧回执必须失效并重新生成。

