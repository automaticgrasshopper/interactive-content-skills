# timeline_edit 工程对接

依据[工程文档](https://j0yswlgboxz.feishu.cn/wiki/HdW5w5ENoiAJoMkuq8RcQXKdnBc)，2026-09-15按更新文档核对。此参考是工具调用合同，不取代业务目标、字幕授权或实际播放验收。

已在nextplay-air后台读取到发布的timeline_edit：实际Input Schema为顶层object/oneOf，直接提交thread_id、operation等字段，不因Studio展示“args”而额外包一层args。发布可见不代表旧会话已刷新或实际调用已通过，仍需运行时核对。

## 能力与职责

调用前确认当前环境实际暴露 `timeline_edit` 且 Schema 支持 `operation`。仅有旧 `thread_id + route_node` 或工具缺失时，报告环境未接通，不混用旧协议，不直接改写 `nextplay/current/route.json` 绕过本入口。工具已开发与当前会话已加载是两回事；旧会话缺新参考时，用正式 skill 加载入口核对版本，不能假称已加载新规则。

Skill 负责定位用户要求的内容、把成片区间映射为保留源区间、选择真实素材及顺序。MCP 负责目标轨道的时间重排、拆分、生成引用和保存。视频与其内嵌原声一体；独立 audio、timed_text 轨均不自动联动。语音识别、补片生成、文字样式描述、日志恢复不属于本工具的计算职责。

一个请求一种操作，一个节点。公共字段：`thread_id`、`operation`、`target_type`，按目标添加 `node_index`、`track_index`、`track_type`、`clip_index`、`params`。不发送 `type`、`close_gap`、`route_node`、`base_route_revision`、路径、凭证或自由操作列表。

## 查询与定位

每条用户编辑请求先query route再query timeline；即使已知节点或只改一条也不省略。AskUser回答属于同一请求，不清空本轮查询证据，但期间发生写入则重新查询。按入口的五步顺序完成后才首写。
```json
{"thread_id":"实际线程ID","operation":"query","target_type":"route"}
```

返回节点目录，利用 `episode_ref`、`node_type`、标题等找到对应集的 `node_index`，不能把第二集直接当下标1。再 `query timeline`（加 node_index），需要时 `query track`（加 track_index）或 `query clip`（再加 clip_index）。查询不传 params。

所有下标从0计数，来自当前原数组，不按类型过滤，不按 order_index 重排序。“第二镜头”先映射正式镜头身份，再查对应的全部片段；一个镜头拆成多片后不能只剪一个。引用用于核对身份，但请求通过下标定位；新引用原样采用成功结果，不编造。

视频和音频写操作使用真实`video`/`audio`类型；字幕请求按统一合同传`timed_text`/`character_intro`/`worldview`业务类型，先定位用户移动后的实际轨道。`target_type` 是对象层级 `route/timeline/track/clip`，不是媒体类型。整组轨道换位不传 track_index/track_type。

## 时间与操作

所有时间为安全整数毫秒，区间 `[start_ms,end_ms)`，`0 <= start_ms < end_ms <= 9007199254740991`。媒体 Timeline 时长等于 Source 时长，不支持变速。用户未特别说明时按上下文中的当前成片时间定位；歧义才问。

| 操作/目标 | params | 语义 |
|---|---|---|
| update/track（audio） | `settings` 内仅 `gain_db`、`muted`，至少一项 | 合并音量/静音，不改时间；数值有限，muted为布尔值，不能null重置 |
| update/clip（timed_text） | `text`、`timeline_range`、`properties`，至少一项；properties更新仅允许subtitle_layout | 保留其他字段；新时间只能包含于该条当前区间，不平移其他字幕 |
| trim/clip（video/audio） | `keep_source_ranges` | 保留当前 source_range 内非空、升序、不重叠区间；相邻段先合并。不传 timeline_range |
| add/clip | `insert_index`、非空 `clips` | 在原数组下标前插入，等于长度为追加 |
| add/track | `insert_index`、`track` | track须有track_type、非空role、非空clips；timed_text还须language，settings按合同可选 |
| delete/clip或track | 不传params | 只移除明确目标的编排引用，不删除源文件；删最后一片仍保留空轨 |
| transposition/clip（video/audio） | `clip_order` | 新位置对应原下标的完整排列，不能重复、遗漏、越界；整对象随素材一起移动 |
| transposition/track | `track_order` | 完整原tracks下标排列，只改数组顺序及order_index，不改片段时间 |

媒体 add 的每片必需真实 `source.media_ref`、有效 `source_range`；已知 asset_ref、generation_ref可带入。不传 timeline_range、clip_ref。新轨不传track_ref、order_index，媒体clip_type由工具生成。新区间不受旧Timeline末尾或旧片段区间限制，但Skill必须核实源媒体真实长度。角色和业务来源等扩展字段不可借properties偷渡；字幕布局仅使用下述正式字段。

字幕 add 的每片必需 `text`、`timeline_range`，布局结构按subtitle-layout-handoff最新统一合同，不传 source/source_range/clip_ref/clip_type；工具生成text类型。字幕按数组时间有序且不重叠，允许空隙，新时间不受旧字幕范围限制。中文字幕的role=`subtitle`、language=`zh-CN`；track_type按统一合同区分三种业务类型，接收端未支持时如实报告，不把介绍改成timed_text；不要误写复数`subtitles`或另造介绍role。已有轨沿用其合法身份，其他语言按实际合同选择。

### 新字幕的插入位置

add/clip的params.insert_index是目标文字轨当前clips数组的插入位置；不是track_index、字幕轨数量，也不是刚查询的clip_index。先query核对该轨原数组按时间有序，再取第一个start_ms大于等于新start_ms的原片段下标，无该片段才用clips.length。写前检验前邻end_ms<=新start_ms、新end_ms<=后邻start_ms；未满足时是实际重叠，不能换一个下标硬塞。需要同期字幕时使用合法独立文字轨，不移动无关字幕。每次成功增删后重新定位，不复用旧下标。

例如当前三条start_ms为6600、12200、13500，新增800–2000ms的insert_index是0；track_index即使为1或2也不改变这个值。此例只说明下标含义，不作为实际项目时间。只构造必需text/timeline_range，不重复提交旧布局；clip_type/clip_ref由MCP生成，不能因为query回显它们就带回add。

字段适配以工具入参、工程文档、产品消费者共同支持的结构为准，不机械复制业务分析对象。发布Schema允许不等于工程可落盘：当前实测字幕add的顶层kind、speaker_ref会触发工程additional property错误，因此本版本字幕新增不发送这两个可选字段，也不为了迁移补造它们。说话人、对白/介绍用途、旧新ID映射保存在runtime后期记录，供内容判断使用，不必进入字幕Clip。字幕新增只组装text、timeline_range和正式subtitle_layout；已有且工程认可的properties按原结构保留，不能把被拒字段搬进properties偷渡。若省略某字段会丢失用户要求的可见效果或真实关联行为，先核对已支持映射，不能静默牺牲效果。

媒体新增同样先用已在当前项目登记的source和source_range，不把业务对象整块透传。当前项目校验也拒绝Clip顶层shot_ref，故不发送；镜头身份通过合法source.asset_ref及内部映射追踪。不将query返回对象直接当add参数；embedded_audio顶层已出现工程拒绝，不提交它。properties只保留当前合同明确接受的原属性，不新增restored_from_trim等标记。原属性无法经合法入口恢复时，在破坏前明确该恢复限制，不先删掉再发现无法恢复。跨项目复用须先以真实媒体回执/地址通过正式入口登记到目标项目，不能把源项目media_ref原样复制后当作目标已登记。clip_ref仍由MCP生成，不假称ID不变。可选字段导致错误时，在用户目标不变、效果不丢失的前提下适配最小有效请求并验证，不立即判为必须改工程；工具生成的必需结构仍不合法或没有保留必要效果的支持路径时，才报告具体工程阻塞。

## Clip级字幕布局

字幕布局以[统一请求合同](subtitle-layout-handoff.md)为准：原MCP外层保留，style为对象、font_size保留，position使用英文括号，track_type业务枚举包含timed_text/character_intro/worldview；不另发第二套消息。先核当前接收端Schema，旧接口未升级时如实报告，不静默回退旧字符串style。其他MCP操作合同不因布局变化而改写。

## 字幕与音乐另行处理

Agent聊天剪视频且已有字幕时，先按[字幕询问](subtitle-interaction.md)确认是否处理，用户明确选择后不重复问。拒绝则整条字幕轨原样保留，不以“保证同步”为由擅自改字幕；交付说明可能不同步。

同意后建立旧事件到保留内容/新Timeline的映射。删掉的文字按实际语音边界处理，不能按被裁时长比例删字。识别工具未就绪时可用现有语音理解能力，但无字级时戳就标明精度，不假造识别回执。

字幕仅改文字/缩短原显示区间用update。构造请求前比较新区间与旧区间：任一边界超出旧范围即不得调用update，包括整条前移/后移；直接规划add/delete，不先试一次必定越界的update。先完整留底、预检所有目标及邻居区间，优先先add验证再delete；新旧重叠导致无法先add时，明确这不是原子替换，留底后逐条delete/add，每条完成即读回并校验工程再继续，避免连续删除后留下缺字幕的中间状态。新增按上面的最小字段规则组装。失败先query确认现状，用已验证能力恢复受影响条目，不盲重放、不继续扩大修改。新clip_ref会变化，记录旧新映射；有关联依赖或原样式无法保留时先报告限制，不假称保持同一ID或强行丢掉属性。不能直接写route兜底。

音乐只在授权范围内独立处理。当前update/track的gain_db/muted仅控制固定音量/静音，没有任意音频绝对定位；不能乱填range、合成静音挤位置或声称静态gain_db就是ducking。现有播放器识别音频Clip.properties.fade_in_ms/fade_out_ms非负整数毫秒并逐帧计算包络，可经Schema支持properties的add/clip或add/track写入，已有音轨按完整留底合法重建；不把audio属性塞给仅支持timed_text的update/clip。按[配乐参考](background-music.md)保留source/时长/原声并实播验证，当前运行时拒绝则恢复并报告实际缺口。无法保持已批准音频入点时报告该部分限制，保留可播放版本。

## 保存、冲突与恢复

编辑前必须将本轮query返回的完整timeline原对象（所有video/audio/timed_text轨、settings、每个clip及其全部属性/引用/源区间/时间/layout）、节点身份与原数组下标、timeline_hash、route_revision、用户要求及区间映射实际写入 `runtime/postproduction_history/<本轮唯一标识>/before.json`，随即重新打开文件、json.loads解析，并断言读回timeline与本轮查询原对象完全相等，成功后才允许首个修改工具。读回可与写入放在同一次exec内，但必须有真实read_text/解析/比较，不能只见write_text exit0就跳到trim。只摘录文字/时间的摘要、历史工具输出或裁后日志都不是完整留底。备份不作为整route写回载荷；日志不是MCP参数。恢复超出当前source_range时不能用trim扩大，需依据原媒体和留底通过支持的add/delete重新编排；没有可靠备份不承诺恢复。

写成功看 `structuredContent` 中完整timeline、timeline_hash、route_revision，并核对isError及目标变化。后续操作使用最新数组；同一节点串行，不用旧下标并行写。服务内部冲突检查不保障早先query版本，也不是端到端原子事务。

校验失败修正原因；冲突重新query和定位。超时、断连或写错误先query确认是否已生效，不能盲重放add/delete/trim/换位。MCP修改后不再让旧完整route快照覆盖结果；其他依赖/媒体登记走各自正式入口，不修改不可变generation来压掉校验错误。

投影依赖修复必须符合真实业务变化。先读取当前依赖和正式同步/重新投影协议，核实本轮是否只改编排而未改媒体；使用已有支持入口刷新，不机械宣称必须重新生成视频。不得通过复制媒体条目、添加带sync后缀的虚构素材或无关写入来迫使revision变化。这类做法即使让校验VALID也不算修复成功。若正式入口不支持真实依赖同步，保留有效时间线与具体错误，不污染资产库；继续检查产品实际读取消费链路以准确界定影响。

读回只证明保存。修改字幕后须使用当前项目提供的只读校验能力检查工程结构及适用的投影合同；先确认校验入口与目标，不猜脚本路径。再刷新产品预览核对事件数、文字、时间、实际呈现及未授权轨道未变。分别记录接口读回、工程有效、产品显示、播放检查；无校验入口或无法访问预览时明确未验证，不能宣布完整成功。版本依赖差异只是待核对线索，未经实际校验不直接判为阻塞。样式另按[排版交接](subtitle-layout-handoff.md)处理；不能把工程描述送出称为位置已生效。


