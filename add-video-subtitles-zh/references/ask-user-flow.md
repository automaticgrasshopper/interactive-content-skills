# Ask User 流程

## 原则

- 使用“两次固定询问 + 条件异常询问”。
- 第一次只决定是否进入字幕流程。
- 第二次一次收齐常规偏好。
- 只有真实异常才追加询问。
- 选项写清影响，推荐项放在第一位。
- 每个问题都提供名为“其他想法”的自由输入入口，让用户可以补充自己的处理方式；收到自定义内容后，先判断是否可在本 Skill 范围内安全执行，能执行则据此继续，存在会改变成片结果的歧义时再用 Ask User 追问。
- 使用稳定 snake_case `id`。
- 本环境的 Ask User 卡片不会为 `type: "boolean"` 渲染可提交控件。所有是/否问题必须使用 `type: "select"` 并显式提供“是/否”两个 `options`；禁止使用 boolean。
- 两次固定询问都属于低自由度协议调用：必须逐字段原样复制各自下方的完整 payload，不得改写问题结构、删减 `options`、把选项只写进 `description`，也不得仅凭自然语言“询问用户”。
- 第一次调用前自检：`questions.length === 1`、`questions[0].type === "select"`、`questions[0].multiple === false`、`questions[0].options.length === 2`，且两个选项都同时含 `label` 和 `value`，问题包含标签为“其他想法”的 `userInput`。任一条件不满足时禁止调用 Ask User。
- 第二次调用前自检：`questions.length === 4`；四个问题的 `id` 依次且只能为 `include_worldview`、`include_character_intro`、`subtitle_language`、`subtitle_font`；每个问题都是 `type: "select"`、`multiple: false`，并且 `options.length` 依次为 `2、2、2、3`。每个选项必须同时含 `label`、`value` 和 `description`，每个问题都包含标签为“其他想法”的 `userInput`。任一条件不满足时禁止调用 Ask User。

## 第一次询问：是否生成字幕

在全部目标分镜视频完成后调用：

```json
{
  "description": "所有目标视频已经完成，需要先决定是否进入字幕流程。",
  "questions": [
    {
      "id": "generate_subtitles",
      "title": "是否生成字幕",
      "type": "select",
      "multiple": false,
      "required": true,
      "description": "所有目标视频已经完成。选择生成后，封面会等待字幕渲染和检查完成；选择跳过则直接进入封面阶段。",
      "options": [
        {
          "label": "是，生成字幕",
          "value": "generate",
          "description": "推荐；继续配置并生成整个视频的字幕。"
        },
        {
          "label": "不生成字幕",
          "value": "skip",
          "description": "不生成字幕，直接进入封面设计环节。"
        }
      ],
      "userInput": {
        "label": "其他想法",
        "placeholder": "填写你希望采用的其他处理方式"
      }
    }
  ]
}
```

只接受选项值 `generate` 或 `skip`。不要改用 boolean，也不要要求用户通过普通聊天消息回答正在等待的 Ask User 卡片。
调用成功后的卡片必须同时可见“是，生成字幕”和“不生成字幕”两个可提交选项，以及“其他想法”输入；若卡片没有选项或自由输入入口，视为协议失败，不得继续字幕流程或声称正在等待用户。

## 第二次询问：字幕配置

只在用户选择生成后调用。调用前先展示`assets/font-options-preview.svg`或等价预览。

```json
{
  "description": "请一次完成字幕内容、语言与字体配置。推荐项均排在第一位。",
  "questions": [
    {
      "id": "include_worldview",
      "title": "世界观开场介绍",
      "type": "select",
      "multiple": false,
      "required": true,
      "description": "是否在唯一入口视频前5秒添加世界规则与本集前情说明。",
      "options": [
        {
          "label": "在第一集添加世界观和前情提要",
          "value": "include",
          "description": "推荐；在第一集开场添加世界规则与本集当前事件的简明说明。"
        },
        {
          "label": "只添加对话字幕",
          "value": "exclude",
          "description": "不添加世界观和前情提要，保留对话字幕；人物介绍仍按下一项选择处理。"
        }
      ],
      "userInput": {
        "label": "其他想法",
        "placeholder": "填写你希望采用的其他开场说明方式"
      }
    },
    {
      "id": "include_character_intro",
      "title": "人物首次出场介绍",
      "type": "select",
      "multiple": false,
      "required": true,
      "description": "是否按每条玩家可达路线，在正式角色第一次真人清晰出场时添加竖排中文姓名与身份。",
      "options": [
        {
          "label": "是，添加",
          "value": "include",
          "description": "推荐；每条可达路线分别判断角色首次真人出场。"
        },
        {
          "label": "否，不添加",
          "value": "exclude",
          "description": "不添加人物姓名与身份介绍。"
        }
      ],
      "userInput": {
        "label": "其他想法",
        "placeholder": "填写你希望采用的其他人物介绍方式"
      }
    },
    {
      "id": "subtitle_language",
      "title": "字幕语言",
      "type": "select",
      "multiple": false,
      "required": true,
      "description": "其他语言默认保留中文并增加目标语言；如需仅目标语言，请在自定义答案中说明。",
      "options": [
        {
          "label": "中文",
          "value": "zh",
          "description": "推荐；只显示正式中文台词。"
        },
        {
          "label": "中英双语",
          "value": "zh_en",
          "description": "中文在上，英文在下。"
        }
      ],
      "userInput": {
        "label": "其他想法",
        "placeholder": "例如：中文加日语；仅日语；或其他语言安排"
      }
    },
    {
      "id": "subtitle_font",
      "title": "字幕字体",
      "type": "select",
      "multiple": false,
      "required": true,
      "description": "请结合上方字体示意和题材选择；所选字体不可用时会自动使用视觉接近且覆盖目标语言的可用字体。",
      "options": [
        {
          "label": "思源黑体",
          "value": "source_han_sans",
          "description": "推荐；中性清晰，小字号和对话字幕可读性最好。"
        },
        {
          "label": "思源宋体",
          "value": "source_han_serif",
          "description": "正式、有叙事感，适合历史、古风和世界观说明。"
        },
        {
          "label": "霞鹜文楷",
          "value": "lxgw_wenkai",
          "description": "温润、有书写感，适合古风、日常和情感题材。"
        }
      ],
      "userInput": {
        "label": "其他想法",
        "placeholder": "填写字体名称或其他排版要求；字体不可用时自动使用同风格替代字体"
      }
    }
  ]
}
```

第二次调用成功后的卡片必须同时满足以下可见条件：

- 可切换查看 4 个问题。
- “世界观开场介绍”有“在第一集添加世界观和前情提要 / 只添加对话字幕”两个可提交选项。
- “人物首次出场介绍”有“是，添加 / 否，不添加”两个可提交选项。
- “字幕语言”至少有“中文 / 中英双语”两个可提交选项。
- “字幕字体”至少有“思源黑体 / 思源宋体 / 霞鹜文楷”三个可提交选项。
- 四个问题都允许通过“其他想法”输入自定义安排。

若任一问题显示“未回答”却没有可点击选项，视为协议失败，不得继续处理、不得让用户改用普通聊天回答，也不得声称正在等待用户。

## 条件询问：无世界观独占开场段

仅在用户选择世界观介绍，且首个入口视频前5秒没有可独占用于说明的环境段时调用。以下任一情况都算没有独占开场段：

- 没有足够安全区。
- 角色本人已清晰出场，世界观会与人物介绍同时显示。
- 已有实际对白，世界观会与对话字幕同时显示。
- 关键动作或剧情信息使观众无法同时阅读世界观。

```json
{
  "questions": [
    {
      "id": "worldview_no_safe_area",
      "title": "世界观字幕位置",
      "type": "select",
      "multiple": false,
      "required": true,
      "description": "入口视频前5秒没有可独占的信息段：直接放置会遮挡关键画面，或与人物介绍、对话字幕同时出现。",
      "options": [
        {
          "label": "为世界观介绍单独生成空镜头",
          "value": "generate_establishing_shot",
          "description": "推荐；使用入口视频真实帧或同制作链场景资产参考生成约5秒无人物、无对白的同画风世界镜头，让世界观说明独占显示；可能会消耗生成视频所需的 token，原视频和字幕整体后移。"
        },
        {
          "label": "在现有视频留白区域添加",
          "value": "use_existing_whitespace",
          "description": "不生成新镜头，直接在现有视频的留白区域添加世界观介绍；必须避开人物、对白字幕、关键动作和产品 UI。"
        }
      ],
      "userInput": {
        "label": "其他想法",
        "placeholder": "填写你希望采用的其他世界观呈现方式"
      }
    }
  ]
}
```

不得在该步骤再次提供“取消世界观介绍”：用户已在上一步确认需要世界观和前情提要。推荐生成独立空镜；用户选择`use_existing_whitespace`时，允许世界观说明与现有画面共用时间段，但字幕文字框必须位于真实留白区域，并与人物介绍、对话字幕、人物脸部、关键动作和产品 UI 在空间上完全避让。若找不到能够通过安全区检查的留白，不得静默取消或强行覆盖；读取“其他想法”，或再次用 Ask User 请用户决定新的呈现方式。

## 字体不可用：自动降级，不询问

字体不可用时不得调用 Ask User。按字体类别与语言覆盖自动选择最接近的可用字体：

1. 优先查找已安装的同系列或同源字体，例如 `Source Han Serif SC` 与 `Noto Serif CJK SC` 互为宋体候选。
2. 本机没有合适字体时，自动安装或下载允许当前用途使用的同风格字体。
3. 下载失败时，继续选择系统内能够完整显示目标语言的同类别字体；宋体降级到其他 CJK 衬线体，黑体降级到其他 CJK 无衬线体，手写体降级到可读的 CJK 楷体或宋体。
4. 渲染前检查全部实际字幕字符；发现缺字、方框或乱码时继续降级，不得向用户索取字体文件。
5. 在私有验收记录中写明请求字体和实际字体，用户可见交付只报告字幕验收结果，不暴露安装过程。

## 状态转换

- 第一次询问前：不要设置`waiting_user`，先完成视频就绪检查。
- 第一次询问已发出：`waiting_user`。
- 用户跳过：`skipped`，放行封面。
- 用户生成且第二次询问已发出：`waiting_user`，阻塞封面。
- 配置完整并开始处理：`in_progress`。
- 异常询问已发出：`waiting_user`。
- 全部验收通过：`completed`，放行封面。
- 不可恢复失败：`failed`，阻塞封面。
