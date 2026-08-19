# 工作流与阶段门禁

本文件是私有产物、依赖顺序和放行条件的唯一调度合同，不增加正式业务字段。

## 第一步：最小创作输入

### 缓存

```text
user-request.md
user-intent-lock.json
creative-brief.json
```

`creative-brief.json`使用`nextplay.episode-creative-brief.v1`：

```json
{
  "contract_version": "nextplay.episode-creative-brief.v1",
  "user_intent_contract_sha256": "当前意图合同摘要",
  "title": "用户端展示标题",
  "logline": "用户端展示的一句话；没有则为null",
  "story_description": "用户端展示的大纲正文",
  "story_volume": "用户端展示的体量原文；没有则为null",
  "assets": {
    "characters": [{"name": "正式名", "description": "展示描述"}],
    "scenes": [{"name": "正式名", "description": "展示描述"}],
    "props": [{"name": "正式名", "description": "展示描述"}]
  },
  "user_constraints": []
}
```

`user_constraints`逐项复制意图合同中全部`required=true`约束，不添加模型解释。三个资产数组允许为空；每项只能有`name`和`description`。

### 生成与验证

调用方把用户端当前可见字段放入临时`VISIBLE_INPUT.json`。该临时文件不进入缓存闭包。依次运行：

```bash
python3 scripts/validate_user_intent_lock.py contract CACHE_ROOT
python3 scripts/build_creative_brief.py VISIBLE_INPUT.json CACHE_ROOT --output CACHE_ROOT/creative-brief.json
python3 scripts/validate_creative_brief.py CACHE_ROOT
```

构建器只执行字段白名单投影；输入中任何额外字段都被丢弃。验证器还会递归拦截节点建议、隐藏主题、隐藏关键事件、隐藏世界规则、结局预算、情绪脊和结构建议字段。三条命令全部PASS后才能进入第二步。

## 第二步：完整故事

### 唯一输入与产物

写作者只读取`creative-brief.json`和`references/complete-story-writing.md`，生成：

```text
complete-story.json
complete-story-review.json
```

`complete-story.json`使用`nextplay.episode-complete-story.v1`：

```json
{
  "contract_version": "nextplay.episode-complete-story.v1",
  "creative_brief_sha256": "creative-brief.json规范化摘要",
  "title": "与创作简报一致的标题",
  "complete_story": "从开场连续写到结局的完整可读故事"
}
```

依次运行：

```bash
python3 scripts/complete_story_gate.py packet CACHE_ROOT --output COMPLETE_STORY_PACKET.json
python3 scripts/complete_story_gate.py seal CACHE_ROOT COMPLETE_STORY_REVIEW.json
python3 scripts/complete_story_gate.py verify CACHE_ROOT
```

冷读逐项检查用户硬约束、连续因果、人物行动、关键发现、结算和体量比较。普通`story_volume`只产生`aligned`、`story-longer-than-signal`或`story-shorter-than-signal`结论；后两者必须给出中性建议，但不得自动删改或扩写故事。用户硬锁体量不匹配时不得seal。

第二步不得创建情绪运动、主线切片、决定裂缝、结局预算、拓扑、节点编号或分集梗概。故事冷读PASS前，第三步全部产物均非法。

## 第三步：主线、开扇与全体梗概

第三步只能从当前有效的`complete-story.json`开始：

```text
complete-story.json
→ mainline-decomposition.json
→ decision-fissure-audit.json + review
→ story-treatment.json + review
→ topology.md
→ route-duration.json
→ topology-review-a.json + topology-review-b.json
→ emotional-spine.json
→ episode-synopses/*.json + review
```

顺序硬约束：先自然切主线，再从已发生事件提取主线情绪运动，随后扫描裂缝并开扇；全图稳定后才统计和编号节点，最后把各路线情绪运动投影到正式节点。主线切片必须按原文顺序无遗漏覆盖完整故事，不得按字数或数量均分。全图至少自然形成一个主结局、一个与其不同的期望结局、一个失败结局和一个小结局；不得按位置或裂缝数量给小结局配额。

普通故事体量和节点建议不得成为第三步参数。用户明确固定N集时，从`user-intent-lock.json/fixed_episode_count`读取并在全图完成后精确校验；自然结构无法命中时返回结构冲突，不得补空节点或合并不相干事件。

拓扑及路线记账通过确定性门禁后，运行`topology_dual_review_gate.py packet`生成唯一封闭材料包。当前任务按`topology-double-review.md`串行完成A、B两遍完整复检；每遍从材料包重新判断，B遍不复制A遍结论。分别封存为`topology-review-a.json`与`topology-review-b.json`；两者均PASS前不得创建情绪脊或分集梗概。

第三步的细节在下一轮调优；在此之前，任何Reference或脚本都不得恢复第二步之前的情绪脊、节点预算或时长上限。

## 第四步：逐集写作与闭包

第三步一次冻结全体梗概后，先用`build_asset_catalog.py`从`creative-brief.json`确定性投影仅含资产名称的校验目录；它不恢复上游隐藏资料。随后按`atomic-run-orchestration.md`推进单集适配源、连续故事材料、短底稿与确定性回执、Enhancer完整复写、结构验收和单集验收。正文不得反向改写完整故事、主线、拓扑或梗概。

四个阶段均由当前任务串行执行。每个安全提交点运行`workflow_state.py CACHE_ROOT`并立即执行唯一`next_actions`；上下文切分后也从该状态恢复，不依赖对话记忆或用户确认。

最终闭包必须绑定：

- `user-request.md`
- `user-intent-lock.json`
- `creative-brief.json`
- `complete-story.json`
- `complete-story-review.json`
- 第三步全部当前有效材料
- 全部分集写作和验收材料
- 最终业务JSON

任一上游文件变化，其下游回执立即失效。只有工程接收层独立取得`DELIVERABLE_ACCEPTED`时才允许投影正式结果。

## 返修边界

- 第一步错误：重建创作简报及全部下游。
- 第二步错误：只返修完整故事并使第三步及以后失效。
- 第三步错误：不得回写完整故事；真实裂缝不足时才退回第二步重新设计故事情境。
- 用户局部编辑已有节点：遵守`canvas-current-state.md`和`local-node-editing.md`，不重跑未授权上游。
- 任何门禁失败都只修最早失败材料及其下游；不得手写PASS或复制旧回执。
