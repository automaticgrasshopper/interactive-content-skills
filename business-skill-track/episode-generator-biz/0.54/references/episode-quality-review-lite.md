# 单集剧本轻量冷读

这是独立于写作者的五项冷读，只判断当前完整剧本能否放行。只读取状态机指定的`episode-review-packets/<episode-id>.json`，不得读取写作过程、其他分集正文、旧审核或预期答案，不得修改、润色或续写剧本。

逐项检查：

1. `concrete_action_chain`：关键进展是否由具体动作、现场反馈和人物调整连续造成，而非摘要代替表演。
2. `situated_dialogue`：对白是否回应眼前人、物和变化；是否存在人物卡登记、任务宣言或万能问答。
3. `time_space_continuity`：每场信息是否能在当前时空被人物感知，换场和人物进入是否有行动承接。
4. `no_meta_registry_or_summary`：正文是否没有制作元话语、角色履历、关系解释、梗概复述和抽象流程骨架。
5. `stop_boundary_and_next_entry`：本集是否完成应有状态变化、没有越过停止边界，并让下一节点入口由当前后果自然成立。

只输出`episode-review-candidates/<episode-id>.json`：

```json
{
  "contract_version": "nextplay.episode-quality-review.v1",
  "episode_id": "与材料包一致",
  "screenplay_sha256": "与材料包一致",
  "reference_sha256": "与材料包一致",
  "covered_checks": [
    "concrete_action_chain",
    "situated_dialogue",
    "time_space_continuity",
    "no_meta_registry_or_summary",
    "stop_boundary_and_next_entry"
  ],
  "status": "PASS或FAIL",
  "issues": []
}
```

PASS时`issues`必须为空。FAIL时只保留一至三个足以阻止放行的关键问题，每项严格使用`{"category":"五项之一","anchor":"正文中的连续原文锚点","reason":"为什么影响可演性或因果"}`。不得给修改稿、逐句建议、评分或额外字段。
