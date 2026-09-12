# 输入输出合同

初次读取用户原话、正式项目身份、游戏企划和相关角色/场景/道具文字资产；没有的创意信息由作者在授权范围内生成。测试身份可按用户要求建立并明确标为测试。剧情与图形均由本Skill负责；完整剧本属于独立编剧Skill。

## 本轮输入

先在独立 CACHE_ROOT 按故事规划写story-core.md，重整主角经历；这份草稿不新增机器合同。再写用户原话、brief和独立故事原文，作者重读通过后才生成切片文件，随后freeze；四份文件从此不变。

`user-request.md`：逐字复制用户实际发出的创作要求，不改写、不补句。企划自己建议的数量、形状和结局，不因用户笼统点击“符合预期，继续”变成硬约束；不能自行写出“我确认了包含四个结局的游戏设置”之类用户没说过的话，再拿它申请豁免。只有用户原话或明确针对该数量/形状的选择，才能作为覆盖默认规则的依据。没有可引用的真实要求就保留默认门禁，不为适配已画好的图制造用户意图。不混入测试执行指令。

`brief.json`：

```json
{"project_id":"真实或明确测试身份","title":"标题","summary":"一句话","duration_minutes":40,"characters":["正式角色名"],"scenes":["正式场景名"],"props":["正式道具名"],"creative_brief":"目标、人物关系、世界规则、必保事实、禁区及情绪和结局走向"}
```

duration_minutes 只作短/非短分类。用户给出时照用，没有时从企划确定；冻结后不得改变。用户原话硬数量由脚本解析，软建议不变成硬限制。

用户明确要求与默认图形冲突时，brief可增加 user_overrides：

```json
{"required_endings":["expected"],"forbidden_endings":["failure"],"ending_quote":"用户关于结局的逐字要求","exemptions":[{"rule":"depth","quote":"用户逐字要求","reason":"该要求为何与默认分岔深度冲突"}]}
```

没有相关用户要求时不填覆盖项。required_endings表示用户明确必需类型，不用来凭空选默认类型。规则名只允许 small、crossing、woven、depth、ending_types、ending_distribution、immediate_result、sustained_growth、continuation_balance、ending_ladder。程序检查引用来自原话，作者负责正确解释，不能引用无关原话豁免。数量不足容纳四类时用户数量优先；无选择按单线生成；完整锁图用逐条对应要求约束正式图，不豁免无关基础合法性。

`mainline-story.md`：按[故事整理](story-development.md)先独立完成的连续主线正文，包含交代清楚第一集的开场及一直到结局的实际事件。无节点编号、路线说明或字段表；作者读过并整理清楚后才切分。新建规划冻结时必须存在，且与mainline.json.complete_story一致（只忽略空白）。旧缓存按原冻结依赖核验，不回填原文冒充曾执行新流程。

`mainline.json`：

```json
{"complete_story":"一条从开场到结局的完整故事原文","episodes":[{"id":"m1","title":"剧集标题","text":"从完整故事逐字切出的连续段落","conflict":"本段实际冲突","stop_boundary":"最后已经发生的事，下一动作尚未执行","characters":["角色名"],"scenes":[],"props":[],"entry_state":{},"state_changes":{}}]}
```

所有episodes.text按序拼接必须覆盖complete_story（只忽略空白）。id在主线与支线全局唯一。人物/资产引用与状态对象由作者填写，状态只读传给下游，不参与机器剧情判断；接口保留可选字段空集合的兼容性，但本轮生成时必须填写正文实际出现的人物、场景和道具，不能以缺省代替整理；未建立的状态不编造。每段对应一个非选择剧集。

## 正式输出

继续使用 nextplay.episode-route-handoff.v1 与 capability_id=episode-route-planner-biz。真结局映射已有 main，不新增平台结局枚举。编剧和平台文件不改。

route_plan.py确定性生成nodes/edges/choices/endings、稳定遍历编号、前后关系及route_material。剧集的单集梗概逐字取源text；选择卡材料只取问题，不含剧情正文。兼容合同所有节点仍标node_type=episode，是否选择由互动节点布尔区分，不能据这个共同字段计集数。

一集 = 一个slot = 一个非选择剧集节点；结局计入集数，选择另计。用户说12集或12个剧情节点就是12个非选择节点；明确包含选择的总卡数才同时锁nodes总数。

正式对象包含项目/路线身份、状态、输入与输出哈希、验收时间及节点材料。材料包含完整故事切片、本集冲突、入口/变化状态、资产白名单、停止边界。内部故事、图形报告、修订历史、用户覆盖说明不写入正式业务字段。正式输出无完整剧本、创作分析或占位正文。

默认完成规划后交接保存；用户仅要求停在PLANNING_ACCEPTED时不写项目；同时明确要求保存到当前项目并展示画布时，只交接已验收路线并完成展示，不扩展到完整剧本。图形验收不证明作者剧情正确，不宣称完成编剧或全剧内容验收。

## 用户编辑后的单集交接

当前画布的删改确认与单集写作材料准备见[当前单集材料绑定](canvas-writing-contract.md)。该模式先完成用户确认的删后接缝整理和当前图基础校验，再绑定当前材料；不回写旧规划哈希，不恢复已删除对象，不放松原保存规则。
