# CLI 与后端正文保存

先读当前绑定 nextplay-cli 的入口及实际 script／asset 文档，使用真实项目身份、当前版本和稳定 ref；不能凭本文件猜命令参数、补密钥或直接改 JSON。读取实际大纲、目标节点、入边、前驱正文与相关资产；已有正文修改取真实读回文本，保留用户手改和无关媒体。

script inspect --node-ref <ref> --include context 取得 episode、predecessors、choices、following、assets、settings 和 missing。上游两套路线方法都用这些真实字段，不要求额外写作包；summary 缺失则回路线补材料。script set/edit 只写 video 正文，选择卡无正文。当前接口 set 输入为 {"text":"当前累计正文"}，资产关联由本集节点 assets 及 CLI 维护；不向 script 请求自造 mentions 字段。新资产先用真实 asset 接口保存 ref，再按当前路线状态更新本集 assets，必要时重读 context。一个有意义的累计正文保存使用独立工具调用，等待结果后继续写，局部修订不覆盖全剧。版本冲突先读当前结果，仅补未成功部分；平台拒绝不能绕过，也不伪造成功回执。

正文实际保存在当前项目 nextplay/current/route.json。完成要同时有实际写入成功，以及从持久化项目读回的目标正文／资产关联 与本次修改相符。可复用 CLI 已给出的真实读回；缺目标内容时用实际 script inspect 或 route inspect 核对。dry_run 不算保存；unchanged 仅在当前内容已经符合时成立。partial_saved 或结果不明先查实际状态，不整批重放。

这里保留工程保存要求，不增设故事写作验证阶段。自然剧情、Thread 草案或前端变化不能替代后端正文；CLI 保存也不证明页面已同步。交付页面结果时确认实际刷新状态，尚未同步准确说明，不能靠调整显示掩盖未保存。画布之外的内部材料不写进正式剧本。

共享 screenplay 文档的旧写作阶段不适用于本 Skill；这里只沿用工程合同。仅补本集资产也应尊重当前规划：活跃计划采用 generate edit，规划 next=done 后普通 route edit；外部用户修改按当前 CLI reconcile，保留手改。既定事件、边或结局需变动先交路线协调，编剧不自行建图。
