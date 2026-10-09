# 同一运行内调度路线与编剧

这是同一 Agent、Thread、项目和当前 Run 内按需加载的工作说明，不是跨会话接力。nextplay-cli 负责工程接口；本 Skill 负责大纲与逐段生长；nextplay-route-planning 负责普通完整拓扑；mazha-screenplay-1008 负责正式剧本。按 modes.md 先定范围和方法，不能同时让两套路线策略接管同一段。

完整拓扑由同事 Skill 按 start/next、故事、切片、全部支线、check、complete 推进；切片真实写入 summary，正式 script 空是正常状态。branch-shape 草案、主线保存或部分 landing 不是全图完成。确认无待展开方向及阻塞，真实 complete 成功、next=done 才完成规划。【一键拓扑】到此停止，即使项目开启形象生成也不编剧或生成媒体。

普通整作文字创作在完整拓扑完成后，不结束 Run 或偷偷另发消息，直接交独立编剧逐个处理已保存 video 节点，包括各分支和结局；choice 不编剧。优先先写实际前驱，汇合读全部合法来路，只补未完成正文，保留手改。逐段生长则保存当前事件、选择与全部即时后果入口及必要文字资产后交编剧，当前单元完成再续下一段；不先造整作空图。

交接只用真实 node_ref、script inspect --include context 返回的 episode.summary/conflict/stop_boundary、predecessors/choices/following、assets/settings 和当前范围。不得依赖只有本 Skill 才有的私有写作包或新增字段；缓存不能代替后端。上游节点的故事切片是事实依据，公开【本集剧情】是本集写法，不是改写全作短故事。

独立编剧采用“实际调研→自然语言本集剧情→直接正式正文→逐段真实保存”，覆盖共享 CLI screenplay 文档的旧五阶段、行动底稿、冷读和复写流程；CLI 的字段、校验、格式和保存合同照常遵守。不得刷旧阶段文案表演进度。

表达改动由编剧完成。确需改变路线事件、选择或连接，交回当前路线方法的局部修复：活跃未完规划使用 generate edit/rewrite-segment，外部手改后按真实 next.route_version reconcile；规划 next=done 后用普通 route edit。不要由编剧越权重建图，或为了写一句话重启 start --new。

单节点完成只是推进点，不提前 final／AskUser／解锁整作编辑。完整拓扑专项、整作联合创作和局部批次分别按各自停止点结束；前端依真实版本与 SSE 展示，Skill 不发明完成布尔值、Slot 或动画状态，不等动画后再执行后端操作。
