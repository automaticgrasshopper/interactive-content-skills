# CLI 与后端正文保存

先读当前绑定 nextplay-cli 的入口及实际 script／asset 文档，使用真实项目身份、当前版本和稳定 ref；不能凭本文件猜命令参数、补密钥或直接改 JSON。读取实际大纲、目标节点、入边、前驱正文与相关资产；已有正文修改取真实读回文本，保留用户手改和无关媒体。

script inspect --node-ref <ref> --include context 取得 episode、predecessors、choices、following、assets、settings 和 missing。上游两套路线方法都用这些真实字段，不要求额外写作包；summary 缺失则回路线补材料。script set/edit 只写 video 正文，选择卡无正文。当前接口用 `script set --node-ref <ref> --text <UTF-8 正文文件路径|->` 保存当前累计正文；正文使用真实换行，不包 JSON、不转义，`--text -` 从 stdin 读取。资产关联由本集节点 assets 及 CLI 维护；不向 script 请求自造 mentions 字段。新资产先用真实 asset 接口保存 ref，再按当前路线状态更新本集 assets，必要时重读 context。一个有意义的累计正文保存使用独立工具调用，等待结果后继续写，局部修订不覆盖全剧。版本冲突先读当前结果，仅补未成功部分；平台拒绝不能绕过，也不伪造成功回执。

## 节点梗概与内部底稿

本集自然剧情保存到 route 节点 summary，前端对应 video.data.plot；正式剧本单独写 script，前端对应 content.script.text。内部 action-draft.md、enhancer-input.txt 不写任一产品字段，不自造底稿字段。

本轮实际新写/实质整理梗概用 route create/revise、presentation=write；targets 为 node:实际node.id，正式稿为 script:同一实际node.id；不能用 CLI node_ref 的任意别名代替，无法取得实际 id 时用 [] 覆盖本轮实际目标。reuse/import 仍 canvas，不为了打字改成新创作。梗概与正式剧本分别有 route / script 任务，先在实际保存梗概前切到 route 阶段，进入正式稿保存前切到 script 阶段；内部底稿和增强输入不新增产品任务。

仅整理原有事件的自然语言表达时，用当前 CLI 支持的 update-node，operations 项为 {"op":"update-node","node_ref":"当前真实引用","changes":{"summary":"当前累计本集梗概"}}。无活跃计划或 next=done 用普通 route edit --input；活跃计划用 route generate edit --input，并按当前合同提供涉及主线修改的 --reason。不重启规划，不改变其他节点、边、事件或停点。读当前完整稿并保留用户手改，按完整句段有意义地累计保存，等待回执再继续，不空写刷进度；已完整时一次保存或复用即可；不把现有完整梗概清空或倒退成短前缀，已有用户稿只整体更新确需改动的部分。写完读回 summary，再取得最新 script context 供底稿冻结；任何新事件、来源、结果或连接变动仍返回路线协调处理。

页面按真实 node.id 定位梗概打字，不按标题或最新节点猜目标。消息中的【本集剧情】标记不是节点保存证明，也不需要独立正文界面。保存不明或冲突先核对真实节点，只有成功落地的梗概才能进入后续底稿；不能只给聊天长文就宣称节点已同步。

正文实际保存在当前项目 nextplay/current/route.json。完成要同时有实际写入成功，以及从持久化项目读回的目标正文／资产关联 与本次修改相符。可复用 CLI 已给出的真实读回；缺目标内容时用实际 script inspect 或 route inspect 核对。dry_run 不算保存；unchanged 仅在当前内容已经符合时成立。partial_saved 或结果不明先查实际状态，不整批重放。

这里保留工程保存要求，不增设故事写作验证阶段。自然剧情、Thread 草案或前端变化不能替代后端正文；CLI 保存也不证明页面已同步。交付页面结果时确认实际刷新状态，尚未同步准确说明，不能靠调整显示掩盖未保存。画布之外的内部材料不写进正式剧本。

共享 screenplay 文档只沿用工程合同；本 Skill 的短底稿与增强复写按自己的参考执行，不恢复共享旧五阶段、冷读或写作验收。仅补本集资产也应尊重当前规划：活跃计划采用 generate edit，规划 next=done 后普通 route edit；外部用户修改按当前 CLI reconcile，保留手改。既定事件、边或结局需变动先交路线协调，编剧不自行建图。
