# Ask User 流程

## 原则

- 封面门禁对每个项目只发出一次固定询问卡片；用私有回执记录决定，禁止重复询问。
- 单次卡片同时包含字幕开关和常规偏好。用户选择跳过时忽略其余偏好并立即放行封面。
- 用户明确要求字幕时，不额外询问是否生成；已有明确偏好直接执行，缺失偏好使用本文默认值。
- 只有会改变成片且无法安全默认的真实异常才追加询问。
- 所有问题使用 `type: "select"`；禁止使用不能正常提交的 boolean 问题。
- 每个问题提供“其他想法”自由输入；能在字幕范围内安全执行时直接吸收。

## 封面前唯一询问

全部项目视频完成、即将进入封面且尚无 `subtitle-cover-gate-v1` 回执时，展示字体预览并原样调用：

```json
{
  "description": "封面生成前请一次决定是否生成字幕及其样式；之后不会重复询问。",
  "questions": [
    {
      "id": "generate_subtitles",
      "title": "是否生成字幕",
      "type": "select",
      "multiple": false,
      "required": true,
      "description": "选择生成后，封面会等待全部字幕烧录和验收完成；选择跳过则直接进入封面阶段。",
      "options": [
        {"label": "是，生成字幕", "value": "generate", "description": "推荐；为全部项目视频生成字幕。"},
        {"label": "不生成字幕", "value": "skip", "description": "本项目跳过字幕，直接进入封面设计。"}
      ],
      "userInput": {"label": "其他想法", "placeholder": "填写你希望采用的其他处理方式"}
    },
    {
      "id": "include_worldview",
      "title": "世界观开场介绍",
      "type": "select",
      "multiple": false,
      "required": false,
      "description": "选择生成字幕时有效；未选择则默认添加。",
      "options": [
        {"label": "添加世界观和前情提要", "value": "include", "description": "推荐；在入口视频开场添加简明说明。"},
        {"label": "只添加对话字幕", "value": "exclude", "description": "不添加世界观和前情提要。"}
      ],
      "userInput": {"label": "其他想法", "placeholder": "填写其他开场说明方式"}
    },
    {
      "id": "include_character_intro",
      "title": "人物首次出场介绍",
      "type": "select",
      "multiple": false,
      "required": false,
      "description": "选择生成字幕时有效；未选择则默认添加。",
      "options": [
        {"label": "是，添加", "value": "include", "description": "推荐；按每条可达路线判断首次真人出场。"},
        {"label": "否，不添加", "value": "exclude", "description": "不添加人物姓名与身份介绍。"}
      ],
      "userInput": {"label": "其他想法", "placeholder": "填写其他人物介绍方式"}
    },
    {
      "id": "subtitle_language",
      "title": "字幕语言",
      "type": "select",
      "multiple": false,
      "required": false,
      "description": "选择生成字幕时有效；未选择则默认中文。",
      "options": [
        {"label": "中文", "value": "zh", "description": "推荐；只显示正式中文台词。"},
        {"label": "中英双语", "value": "zh_en", "description": "中文在上，英文在下。"}
      ],
      "userInput": {"label": "其他想法", "placeholder": "例如中文加日语或仅日语"}
    },
    {
      "id": "subtitle_font",
      "title": "字幕字体",
      "type": "select",
      "multiple": false,
      "required": false,
      "description": "选择生成字幕时有效；未选择则默认思源黑体。",
      "options": [
        {"label": "思源黑体", "value": "source_han_sans", "description": "推荐；清晰且适合对话字幕。"},
        {"label": "思源宋体", "value": "source_han_serif", "description": "正式、有叙事感。"},
        {"label": "霞鹜文楷", "value": "lxgw_wenkai", "description": "温润、有书写感。"}
      ],
      "userInput": {"label": "其他想法", "placeholder": "填写字体名称或排版要求"}
    }
  ]
}
```

调用前校验：`questions.length === 5`，ID 顺序必须为 `generate_subtitles`、`include_worldview`、`include_character_intro`、`subtitle_language`、`subtitle_font`；第一题必填，其余四题可选；选项数量依次为 `2、2、2、2、3`；每题都有“其他想法”。卡片缺少任一结构时视为协议失败。

用户选择 `generate` 且未回答可选项时，统一使用：世界观 `include`、人物介绍 `include`、语言 `zh`、字体 `source_han_sans`。用户选择 `skip` 时忽略其余回答。

调用成功或用户此前已明确决定整个项目是否生成字幕后，保存私有 `subtitle-cover-gate-v1` 回执，至少记录项目 ID、决定、偏好、目标视频媒体版本集合和时间。存在有效回执时不得再次发出封面询问；媒体变化只使字幕计划失效，不使“是否生成”的决定失效，沿用原偏好重烧录。

## 用户在任意阶段明确调用

- 只要求“给这个/这些视频加字幕”且没有其他偏好：处理当前指定且已完成的视频，默认仅对话字幕、中文、思源黑体。
- 明确要求整个项目加字幕：可把该决定保存为 `subtitle-cover-gate-v1`，封面前不再询问；缺失偏好默认世界观和人物介绍均添加、中文、思源黑体。
- 明确给出语言、字体、世界观或人物介绍要求：直接采用，不再次确认。
- 当前没有已完成且可读取的目标视频：报告等待项；之后目标视频完成时继续，不把等待误记为失败。
- 明确要求游戏标题、片名、标题帧或海报帧：直接触发标题能力，不修改封面前固定5问。未指定时采用自动模式、正式项目名、项目视觉语言和3000毫秒；只有标题真源无法确定时才询问。

## 条件询问：无世界观独占开场段

仅在用户选择世界观介绍，且入口视频前5秒没有可安全使用的信息段时调用：

```json
{
  "questions": [
    {
      "id": "worldview_no_safe_area",
      "title": "世界观字幕位置",
      "type": "select",
      "multiple": false,
      "required": true,
      "description": "入口视频前5秒没有可安全独占的信息段。",
      "options": [
        {"label": "生成独立空镜头", "value": "generate_establishing_shot", "description": "使用真实帧或同制作链资产作为参考生成约5秒空镜。"},
        {"label": "使用现有留白区域", "value": "use_existing_whitespace", "description": "不生成新镜头，在验证后的留白区域添加。"}
      ],
      "userInput": {"label": "其他想法", "placeholder": "填写其他可执行呈现方式"}
    }
  ]
}
```

不得未经用户同意生成新镜头。选择现有留白但无法通过安全区检查时，继续请求可执行方案，不能静默取消或覆盖关键画面。

## 字体不可用

不询问用户。按字体类别和语言覆盖自动选择最接近的可用字体；必要时下载允许使用的字体。渲染前检查全部实际字符，缺字、方框或乱码时继续降级，并在私有验收记录中写明请求字体与实际字体。

## 状态转换

- 封面询问已发出：`waiting_user`。
- 用户跳过：`skipped`，保存回执并放行封面。
- 用户生成或任意阶段明确调用：`in_progress`。
- 目标视频尚未完成：保持可恢复等待，不记为 `failed`。
- 异常询问已发出：`waiting_user`。
- 全部目标验收通过：`completed`；封面门禁范围内同时放行封面。
- 不可恢复失败：`failed`；封面门禁范围内继续阻塞封面。
