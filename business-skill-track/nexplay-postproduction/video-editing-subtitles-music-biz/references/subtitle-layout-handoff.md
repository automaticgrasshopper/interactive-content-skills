# 字幕布局：统一请求合同

需要显式提交字幕布局时，只使用下面一套完整结构。人物说话字幕（timed_text）未被用户指定样式或位置时使用工程默认配置，不主动提交可选布局覆盖；默认位置为画面下方居中。当前工具若要求显式布局，必须读取工程已确认的默认配置原值，不能用下方人物姓名示例或自行猜测的值替代；具体见[字体与样式能力](subtitles.md)。保留原MCP外层thread_id、operation、target_type、节点/轨道/片段下标、track_type与params.properties.subtitle_layout。style改为对象，font_size仍保留字符串。没有独立subtitle_style字段，没有第二份精简布局，也不另发扁平后端消息。

## 类型、位置与内容

对白／旁白和人物介绍的text（含译文）在最终载荷构造前执行[句号清理与标点校验](subtitles.md)，均不得有句号；世界观及其译文允许保留句号，不纳入清理。写后query实际text并逐条复查，残留必须修正并重新读回，不能仅凭请求成功交付。

track_type业务枚举固定为timed_text（对白）、character_intro（人物介绍）、worldview（世界观）。首次按三类分别安排轨道，不要求用户知道内部类型或下标。用户拖动后字幕用途保留，先query当前timeline，结合字幕标识、clip_ref/track_ref、内容与项目身份重新定位，不使用旧下标、不强行搬回原轨。subtitle_id只在目标Clip内唯一，不能单独跨项目寻址。

人物姓名与身份分别为独立片段和独立轨道，均为character_intro；世界观中文与存在时的目标语言译文按每个显示行分别为独立片段和独立轨道，均为worldview；是否默认附英文按世界观内容分类与语言规则判断，不默认所有故事双语。每个世界观text只放一个显示行，行数决定所需物理轨道数，三种业务类型不限制轨道数量。按[介绍排版](intro-layout.md)协调各行各列位置、字号、时间与世界观/人物互斥。对白按真实语句和时间分片；每片段只提交一份完整布局。

## 完整更新示例

示例展示未指定样式时的姓名默认44px/white；已有用户配置必须优先保留，不照抄示例重置。以下用于已有片段；线程、下标、姓名身份、字体和位置均须用实际项目替换，不能将示例索引当作已存在目标。只改布局不修改原显示时间。

```json
{
  "thread_id": "thread-1",
  "operation": "update",
  "target_type": "clip",
  "node_index": 1,
  "track_index": 2,
  "clip_index": 0,
  "track_type": "character_intro",
  "params": {
    "properties": {
      "subtitle_layout": [
        {
          "subtitle_id": "character-intro-xuning-episode-001",
          "text": "许宁",
          "font": "宋体",
          "style": {
            "fontSize": 44,
            "opacity": 100,
            "preset": "white",
            "scale": 100
          },
          "font_size": "44",
          "position": "(65%，12%)",
          "writing_mode": "Upright"
        }
      ]
    }
  }
}
```

## 字段规范

- 保留subtitle_id、text、font、style、font_size、position、writing_mode。style是对象，不再使用旧样式描述字符串；也不改名为subtitle_style。
- font是实际可用字体名。font_size是1080p基准像素数字符串，style.fontSize是同一数值的数字，二者同时保留且一致。
- style.preset固定枚举：white | outline | peach | mint | purple | red | glow | lime。8个小写标识代表完整样式方案，不是单独颜色，不自行新增。
- style.opacity为不透明度百分比；style.scale为整体缩放百分比，100为原比例。具体数值范围按工程合同，不猜。
- 世界观逐行左边缘对齐、人物竖排顶部对齐均通过各片段position计算实现，新建这两类布局不传style.render.align；不新增anchor、align或bottom_fraction字段。用户已有样式只在授权范围内调整。
- position严格使用英文半角括号(和)，例如"(65%，12%)"；中间沿用中文逗号，百分号为%。当前position按文字框中心锚点解释，坐标是中心X/实际视频宽、中心Y/实际视频高的百分比，不是文字框左上边缘，也不是播放器外框。世界观边距和人物顶部对齐均须按实际文字框宽高换算中心坐标，见[介绍排版](intro-layout.md)；render.align未实际生效时不能据此假定锚点已改变。不传中文全角括号，不把留白解释塞入坐标值。
- writing_mode枚举Horizontal（横排）、Upright（竖排）。横排换行仍用Horizontal，不用逐字空格伪造竖排。
- 新增、改时间、删除与其他操作仍按实际工具合同提供必需字段；本例不含时间修改。新增片段必须有实际文字和时间，不编造clip_index。仅改布局时未涉及的文字、时间、视频、音乐与其他轨道不动。

## 工程接入和验收

上面是用户最新确定的统一请求结构，覆盖旧七字符串与两套交接方案。实际执行前读取当前工具Schema：若仍只接受timed_text和字符串style，则说明当前接收端尚未支持统一结构，不把它冒充已经支持；不悄悄拆成两套消息、不转换回旧布局、不直接写route或猜HTTP接口。可保留这一份完整请求供接入核对。与本布局无关的查询、剪辑、音频操作按现有合同继续执行。

请求已输出、工具已接受、实际保存、刷新后显示分别记录；不能把JSON输出当后端成功。核对真实请求只有这一套外层，style为对象、无subtitle_style、font_size保留、英文括号和三类业务值正确。后端未确认接收时不宣称布局生效。

世界观与人物介绍均仅放在已有视频可编辑字幕轨，按[介绍排版](intro-layout.md)验收分轨、字号、方向、位置、翻译和跨类型时间互斥。姓名示例只代表姓名片段；身份须用其真实目标和38px单独提交。不能烧录、生成文字图片、补视频、重做原视频或修改网页CSS假装成功。
