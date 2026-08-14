# 三阶段分集流水线合同

## 执行模型

一次用户任务由当前任务担任协调者，三个阶段分别在全新的子任务上下文中执行：

1. `episode-branch-planner-biz`
2. `episode-screenwriter-biz`
3. `episode-script-validator-biz`

协调者不得亲自生成完整故事、拓扑、梗概、原稿、增强稿或正式业务JSON，也不得在同一上下文中预先读取三个Skill的正文。每个阶段必须使用子任务调度工具创建新子任务；不传`threadId`，不复用上一阶段子任务。子任务只读取本阶段Skill、当前阶段票据和已验证交接中允许的文件。

用户只看到一次连续生成。阶段切换不要求用户回复，不增加确认点。

## 协调者模式

用户请求初次生成、结构修改或完整重做，且当前任务没有`STAGE_WORKER:<stage>`标记时，执行协调者流程：

1. 在新的缓存目录运行`pipeline_guard.py init`。
2. 为`planning`签发票据，创建全新规划子任务。子任务提示只包含用户目标、项目文件位置、缓存目录、票据路径和`STAGE_WORKER:planning`。
3. 规划子任务返回后，运行`pipeline_guard.py accept planning`。未输出`PLANNING_STAGE_ACCEPTED`不得签发写作票据。
4. 为`writing`签发票据，创建全新写作子任务。提示只包含缓存目录、票据路径和`STAGE_WORKER:writing`，不得复制完整聊天历史或规划答案。
5. 写作子任务返回后，运行`pipeline_guard.py accept writing`。未输出`WRITING_STAGE_ACCEPTED`不得签发校验票据。
6. 为`validation`签发票据，创建全新校验子任务。提示只包含缓存目录、票据路径和`STAGE_WORKER:validation`。
7. 校验子任务必须生成正式三件套和`projection-authorization.json`。协调者运行`pipeline_guard.py projection-verify`，只有独立输出`PROJECTION_AUTHORIZED`才允许调用任何项目写入、路线转换、正式slot或完成态。

子任务工具不可用或连续失败时保持当前阶段，不退回同一上下文代写。

## 子任务模式

阶段子任务必须先用票据运行：

```bash
python3 scripts/pipeline_guard.py claim <planning|writing|validation> --state <缓存目录>/pipeline-state.json --ticket <阶段票据.json>
```

未取得`*_WORKER_CLAIMED`立即停止。子任务只执行标记对应的一个阶段：

- 规划子任务只生成规划产物和`planning-handoff.json`。
- 写作子任务只生成逐集原稿链和`writing-handoff.json`。
- 校验子任务只生成逐集增强验收链、正式三件套和投影授权。

子任务完成本阶段后返回协调者，不自行加载或执行下一Skill，不直接写项目路线。

## 阶段状态

- 规划阶段：`planning-handoff.json`实际生成、绑定当前`pipeline_run_id`并通过验证，才可取得`PLANNING_ACCEPTED`。
- 写作阶段：`writing-handoff.json`实际生成、绑定当前规划交接和`pipeline_run_id`并通过验证，才可取得`WRITING_ACCEPTED`。
- 校验阶段：`episode-business.json`、`completion-receipt.json`和`episode-handoff.json`同时存在，`verify_deliverable.py`实际输出独立一行`DELIVERABLE_ACCEPTED`，才可生成投影授权。

`STRUCTURE_PASS`只说明九字段结构可解析。`NOT_A_COMPLETION_ATTESTATION`出现时必须停止在校验阶段；不得保存路线、输出正式slot或报告完成。

## 正式输出和投影

第一、二阶段不得创建、覆盖、返回或投影正式业务结果。第三阶段是正式九字段结果的唯一生产者。

正式项目写入只能以已授权的`episode-business.json`为源。禁止从以下内容转换或投影：

- `work_episode_raw.json`或其他批量候选JSON
- 聊天中手写的九字段结果
- 只有`STRUCTURE_PASS`的结果
- 缺少任一交接、逐集回执或正式三件套的结果

项目写入后只做读回核对，不得用工程route反向补造内部凭证。

## 修改路由

- 节点增删、移动、重连，或修改选择、分支、汇合、结局：从规划阶段启动新的受影响范围流水线。
- 拓扑与梗概不变，只修改某集剧情表达或对白：从写作阶段启动新的受影响范围流水线。
- 原稿与冻结事实不变，只要求增强、检查或修复表达：从校验阶段启动新的受影响范围流水线。

三种模式最终都返回当前完整九字段结果；未授权内容保持不变。

## 对用户边界

只使用`正在生成故事`、`正在生成分支`、`正在生成剧本`和`正在最终验收`四种状态。不得暴露Skill名、子任务、票据、交接、哈希、缓存、门禁或内部阶段编号。
