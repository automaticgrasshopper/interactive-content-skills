# 原子执行与逐集闭包

本文件只规定阶段三、阶段四怎样推进、隔离、提交、返修和完成。故事、拓扑、梗概、编剧表达和复检判断分别遵守对应 Reference；本文件不重复内容标准。

## 唯一协调器

- 当前任务是唯一协调器，持有`run-state.json`、确定性门禁、哈希、正式文件和最终组装权。
- 新任务初始化一次；已有`run-state.json`时禁止重新初始化。每次动作前和每次上下文恢复后先运行`run_state.py status`，只执行持久化的`next_episode_id`和`next_actions`，不得按说明文字或对话记忆自行推断状态。
- 一次只领取、执行和提交一个原子动作。不得创建循环处理全部剩余集数的临时脚本，不得让一个子任务完成整集链或多集链，也不得先批量生成正文再补回执。
- 每个动作必须先用`run_state.py claim`领取标准输入、`input_sha256`、owner和有期限租约；提交时必须满足`scripts/action_contracts.py`定义的全部且仅有输出。
- 每次状态转换都必须原子写回`status`、`accepted_count`、`total_count`、`next_episode_id`、`next_actions`和`active_leases`。当前动作安全落盘后仍有后续工作时保存`IN_PROGRESS`；余量未知不等于失败，已验收分集不得重写。
- 阶段状态只是用户可见进度，不是任务终点。仍有`next_actions`时不得用阶段摘要结束长任务，不得等待用户确认“是否继续逐集制作”；同一运行应立即领取下一原子动作。若平台强制切分运行，必须以`IN_PROGRESS`和机器可读的下一动作触发续跑，不得依靠用户再次发送“继续”。

## 子任务隔离与提交

只把以下单一动作交给彼此隔离的子任务：Screenwriter、Enhancer、场面复检、普通观众冷读和受控局部修复。Screenwriter与Enhancer串行；两项只读复检在结构门禁后可以并行。

默认父子任务文件系统互相隔离。父任务必须把动作名、分集编号、claim返回的`input_sha256`和该动作的标准输入正文一并发送；子任务只返回绑定相同哈希的`nextplay.episode-child-result.v1`对象。父任务必须把原始返回交给`commit_child_result.py`验证和落盘，不得手工摘取`content`、猜测字段、改写返回或直接写正式文件。子任务不得写状态、回执或正式项目文件。

只有双向哨兵探针证明共享文件系统时才可传路径：父任务写随机nonce，子任务读回并另写回执，父任务再次读回一致才算共享。探针未执行、失败或结果未知时一律使用消息传输；不得用glob搜索其他任务、复制manifest或把父路径硬编码到子任务。

task审批、分配、消息或Runtime超时属于编排失败，使用`run_state.py fail --kind orchestration`或`abandon`登记，不计正文复写。租约超时可以回收；同一动作连续三次编排失败后，下一次必须改用父端安全执行、消息传输或保存`IN_PROGRESS`。任何超时都不是PASS。

正文或语义门禁失败才使用`--kind content`；同一内容动作连续三次失败才熔断。不得把失败写成PASS，也不得删除仍有效的回执。

## 阶段三读取边界

- 单集适配只读取`episode-adaptation-sources/<episode-id>.json`和`episode-story-adapter.md`。
- Screenwriter只读取通过门禁的`episode-writing-inputs/<episode-id>.txt`、`vimax-screenwriter.md`和`chinese-dialogue-craft.md`。标准写作输入已含本集角色的公开身份、关系、知情与能力边界；公开身份用于自然建立观众认知，边界只限制事实，不是必须说出的台词。
- Enhancer只读取脚本生成的`enhancer-inputs/<episode-id>.txt`；该文件必须逐字包含当前草稿、停止边界、`vimax-script-enhancer.md`和完整`chinese-dialogue-craft.md`。
- 场面复检只读取`dramatization_gate.py packet`生成的当前集复检包；冷读只读取`episode_quality_gate.py packet`生成的当前集复检包。两者只判不改，彼此不得读取对方结论。
- 两项复检至少一项失败时，局部修复Enhancer只读取`review-repair-inputs/<episode-id>.txt`；其中只含当前增强稿、合并问题单、停止边界和`vimax-local-repair.md`。
- Screenwriter原稿完成后才读取`character-appearance-validation.md`提取首次出场证据。
- 题材标签命中时才读取`genre-direction.md`；当前集出现推动剧情的书面信息时才读取`written-text-to-dialogue.md`。
- 情绪脊、完整故事、验证脚本、证据格式、旧稿、旧审稿意见和无关路线不得进入Screenwriter或Enhancer工作区。更早已放行正文只保留为证据；除当前集的直接前置真实结尾外，不再进入活跃上下文。

## 逐集状态转换

按冻结拓扑顺序一次只处理一集；当前集的全部直接前置必须已经通过。每个编号都是可独立落盘和续跑的状态转换。

1. 运行`build_episode_adaptation_source.py`建立当前集适配源。该源不读取、依赖或生成过程链。
2. 按`episode-story-adapter.md`生成二至六个连续自然段的故事材料和一句停止边界。当前集只保留自己的变化，不提前演出直接后续独占的动作、核验、选择或结果。
3. 运行`build_episode_writing_input.py`。材料含清单、验收术语或停止边界无效时不得进入写作。
4. 领取`WRITE_DRAFT`，让全新Screenwriter只读取标准写作输入；用`commit_child_result.py`提交原始JSON。随后领取`VALIDATE_DRAFT`，验证原稿并确定性生成Enhancer输入。
5. 领取`ENHANCE`，让另一全新Enhancer只读取标准Enhancer输入；用`commit_child_result.py`提交增强稿。Enhancer可全面重写场面动作、对白、话轮、停顿与反应，但不得改变冻结事实、行动结果、选择、结局或停止边界。
6. 把增强稿原样装入`episodes/<episode-id>.md`和九字段单集对象；正文必须与`enhanced-screenplays/<episode-id>.md`逐字一致。随后提取首次出场证据。
7. 领取`VALIDATE_STRUCTURE`，运行`episode_structure_gate.py seal`；正式对象和结构回执一起提交。Acceptance以后只核对回执哈希，不重放结构门禁。
8. 领取`PREPARE_REVIEWS`，确定性建立场面计划和两份标准复检包。分别领取`REVIEW_DRAMA`和`REVIEW_COLD_READ`，交给两个全新只读子任务。
9. 两份复检原始结果都由`commit_child_result.py`提交。PASS结果的`content`是对应gate可验收的JSON且`findings=[]`；FAIL结果的`content`只含`rewrite_required`，`findings`必须含行号、原文锚点和原因。两项PASS时直接进入`REVIEWS_PASSED`，不得制造空的`MERGE_FINDINGS`。
10. 至少一项失败时，用`review_repair_gate.py merge`合并失败问题单与通过回执，再用`input`生成唯一局部修复输入。隔离Enhancer只改命中行或相邻接缝，未授权行逐字不变；提交时同步更新增强稿、正式正文、修复回执和状态。
11. 局部修复后，旧结构、场面和冷读回执全部失效；从结构门禁重新执行，直到两项复检均PASS。不得为了过检把问题改成压缩旁白、举证句或人物轮流汇报。
12. 只有状态为`REVIEWS_PASSED`时运行`episode_acceptance.py`。它只核对已提交动作的标准路径和SHA-256，不重放结构、场面、冷读或Enhancer门禁。Acceptance后切换下一集。

若合并问题单标记`rewrite_required=true`，不得调用局部修复；运行`run_state.py rewrite`归档当前失败尝试，回到当前集Screenwriter，重新经过完整Screenwriter、Enhancer、结构和双复检。任何覆盖整集的修改都必须走这条恢复边，复检者和Acceptance都不得生成第三版正文。

内容没有变化而正式对象、结构回执、复检包或Acceptance绑定损坏时，不得重写正文或全量重置。分别使用`technical-recover`的`RESEAL_STRUCTURE`、`REPREPARE_REVIEWS`或`REBIND_ACCEPTANCE`回到最小确定性步骤；适配源本身损坏时使用`REBUILD_ADAPTATION`。阶段二回执仅格式或复检元数据变化、内容叶不变时自动保持绑定；单集梗概内容叶变化时运行`rebase-stage-two`，只让该节点及其后继失效。全局故事、拓扑或情绪内容变化不得伪装成局部技术修复。

## 当前集命令

```bash
python3 scripts/run_state.py status CACHE_ROOT
python3 scripts/run_state.py claim CACHE_ROOT EPISODE_ID ACTION --owner OWNER
python3 scripts/commit_child_result.py CACHE_ROOT EPISODE_ID CHILD_ACTION CHILD_RESULT.json --lease LEASE
python3 scripts/run_state.py complete CACHE_ROOT EPISODE_ID PARENT_ACTION --lease LEASE --output OUTPUT [--output OUTPUT ...] [--outcome PASS|FAIL]
python3 scripts/run_state.py abandon CACHE_ROOT EPISODE_ID ACTION --lease LEASE --reason "编排失败原因"
python3 scripts/run_state.py fail CACHE_ROOT EPISODE_ID ACTION --lease LEASE --kind content --reason "内容失败原因"
python3 scripts/run_state.py rewrite CACHE_ROOT EPISODE_ID --reason "整集重写原因"
python3 scripts/run_state.py technical-recover CACHE_ROOT EPISODE_ID RESEAL_STRUCTURE --reason "技术绑定修复原因"
python3 scripts/run_state.py rebase-stage-two CACHE_ROOT --reason "阶段二局部内容叶变化原因"
python3 scripts/build_episode_adaptation_source.py CACHE_ROOT EPISODE_ID --output CACHE_ROOT/episode-adaptation-sources/EPISODE_ID.json
python3 scripts/build_episode_writing_input.py ADAPTATION_SOURCE.json STORY_MATERIAL.json EPISODE_ID --output CACHE_ROOT/episode-writing-inputs/EPISODE_ID.txt
python3 scripts/validate_screenwriter_draft.py CACHE_ROOT/screenplay-drafts/EPISODE_ID.md --episode-id EPISODE_ID --receipt CACHE_ROOT/screenwriter-receipts/EPISODE_ID.json
python3 scripts/build_enhancer_input.py CACHE_ROOT/screenplay-drafts/EPISODE_ID.md --boundary "STOP_BOUNDARY" --enhancer-reference references/vimax-script-enhancer.md --dialogue-reference references/chinese-dialogue-craft.md --screenwriter-receipt CACHE_ROOT/screenwriter-receipts/EPISODE_ID.json --output CACHE_ROOT/enhancer-inputs/EPISODE_ID.txt
python3 scripts/episode_structure_gate.py seal CACHE_ROOT EPISODE_ID
python3 scripts/dramatization_gate.py plan CACHE_ROOT EPISODE_ID
python3 scripts/dramatization_gate.py packet CACHE_ROOT EPISODE_ID --output CACHE_ROOT/review-packets/EPISODE_ID.dramatization.json
python3 scripts/dramatization_gate.py seal CACHE_ROOT EPISODE_ID DRAMA_PASS.json
python3 scripts/dramatization_gate.py verify-one CACHE_ROOT EPISODE_ID
python3 scripts/episode_quality_gate.py packet CACHE_ROOT EPISODE_ID --output CACHE_ROOT/review-packets/EPISODE_ID.cold-read.json
python3 scripts/episode_quality_gate.py seal CACHE_ROOT EPISODE_ID COLD_READ_PASS.json
python3 scripts/episode_quality_gate.py verify-one CACHE_ROOT EPISODE_ID
python3 scripts/review_repair_gate.py merge CACHE_ROOT EPISODE_ID DRAMA_FINDINGS_OR_RECEIPT.json COLD_READ_FINDINGS_OR_RECEIPT.json --output CACHE_ROOT/merged-review-findings/EPISODE_ID.json
python3 scripts/review_repair_gate.py input CACHE_ROOT EPISODE_ID CACHE_ROOT/merged-review-findings/EPISODE_ID.json --reference references/vimax-local-repair.md --output CACHE_ROOT/review-repair-inputs/EPISODE_ID.txt
python3 scripts/review_repair_gate.py verify CACHE_ROOT EPISODE_ID CACHE_ROOT/repair-baselines/EPISODE_ID.md CACHE_ROOT/merged-review-findings/EPISODE_ID.json --receipt CACHE_ROOT/review-repair-receipts/EPISODE_ID.json
python3 scripts/episode_acceptance.py CACHE_ROOT EPISODE_ID
```

`review_repair_gate.py`只在至少一项复检失败时运行。每集通过必须同时满足：适配材料绑定冻结梗概；写作输入不含清单、证据或内部结构；增强稿与正式正文逐字一致；九字段结构、拓扑、资产、首次出场和停止边界一致；两份独立复检回执绑定当前正文；单集Acceptance完整。

## 阶段四闭包

全部分集放行后只执行轻量项目闭包，不再逐集重放语义门禁：

```bash
python3 scripts/stage_two_acceptance.py verify CACHE_ROOT
python3 scripts/validate_character_appearances.py CACHE_ROOT --asset-catalog CACHE_ROOT/asset-catalog.json --introductions CACHE_ROOT/character-introductions.json
python3 scripts/episode_acceptance.py CACHE_ROOT --all
python3 scripts/run_state.py status CACHE_ROOT
python3 scripts/assemble_business_output.py CACHE_ROOT OUTPUT/episode-business.json --completion-receipt OUTPUT/completion-receipt.json --handoff OUTPUT/episode-handoff.json
python3 scripts/validate_business_output.py OUTPUT/episode-business.json --asset-catalog CACHE_ROOT/asset-catalog.json --expected-endings E --expected-formal F --expected-failure X
python3 scripts/verify_deliverable.py CACHE_ROOT OUTPUT/episode-business.json OUTPUT/completion-receipt.json OUTPUT/episode-handoff.json
```

`E`是主要结局总数，必须等于主要正式结局数`F`加主要失败结局数`X`；独立小结局不计入三者。

组装器只映射已验证内容，不得新增、改写或摘要剧本，并须原子生成`episode-business.json`、`completion-receipt.json`和`episode-handoff.json`。任一绑定内容变化时完成凭证立即失效。`validate_business_output.py`的结构通过不代表完成；工程接收层必须自行运行`verify_deliverable.py`，同时取得当前三件套、退出码0和独立一行`DELIVERABLE_ACCEPTED`，才可标记完成和正式投影。否则只能保持`正在生成中`。
