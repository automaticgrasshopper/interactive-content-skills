# 用户意图内部合同

本合同只保护用户明确说出的必保要求，不收录上游建议、展示大纲中的普通叙述、Skill偏好或模型推断。

## 建立顺序

先把本轮用户要求逐字保存为`user-request.md`，再生成：

```json
{
  "contract_version": "nextplay.user-intent-lock.v2",
  "source_sha256": "user-request.md的SHA-256",
  "resolution_status": "resolved",
  "fixed_episode_count": null,
  "constraints": [
    {
      "constraint_id": "user-001",
      "statement": "用户明确要求保留或禁止的内容",
      "scope": ["global"],
      "required": true,
      "forbidden_literals": []
    }
  ],
  "conflicts": [],
  "resolutions": []
}
```

## 登记规则

- 只登记用户明确提出的故事事实、人物关系、禁改内容、选择、结局或体量要求。
- `fixed_episode_count`只有在用户明确说“固定为 N 集”“必须恰好 N 集”等同义表达时才是正整数；其他情况必须为`null`。
- 不得出现`node_count_hint`字段或把上游节点建议改名写入`constraints`。
- 用户明确锁定故事体量时，保留其原话作为硬约束；不要预先转换成节点数。
- `scope`使用`global`、`topology`或冻结后的`episode-xxx`。
- `forbidden_literals`只保存用户明确禁止且需要逐字拦截的词句。
- 合同和源文本均为私有缓存，不进入业务JSON。

## 冲突处理

可以同时成立的要求全部保留。新要求明确修订旧要求时，在`resolutions`中登记`superseded`并只保留当前有效约束。

无法同时成立且会改变故事事实、人物关系、选择、结局、固定集数或硬体量时，将`resolution_status`设为`needs-user`，记录一个中性问题和互斥选项，然后停止生成。用户回答后更新有效约束、保留解决记录并恢复`resolved`。

只有`constraints`中两条或以上当前有效的用户硬约束彼此不能同时成立，才属于本节冲突。上游建议、展示大纲中的数量、普通`story_volume`、Skill要求的结局类别、模型推导的最小节点数或模型偏好都不能与用户要求组成冲突，不能触发AskUser，也不能生成“推荐N节点”的选项。

## 下游绑定

`creative-brief.json`逐项复制全部`required=true`约束，并绑定当前合同摘要。`complete-story-review.json`必须逐项给出故事证据或明确说明禁止项的检查范围。用户要求变化后，创作简报、完整故事及其全部下游立即失效。
