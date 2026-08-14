# 渲染与质量检查

## 私有计划合同

使用`nextplay.video-subtitles.v1`。计划只存在于私有工作区或临时目录，不写入公开 Sheet 字段或 Canvas。交付和修改时同时遵守`delivery-and-versioning.md`。

最小结构：

```json
{
  "contract": "nextplay.video-subtitles.v1",
  "status": "in_progress",
  "settings": {
    "language_mode": "zh",
    "target_language": "",
    "font_key": "source_han_sans",
    "font_name": "Noto Sans CJK SC",
    "font_file": "",
    "include_worldview": true,
    "include_character_intro": true,
    "background_mode": "none",
    "worldview_placement_mode": "generated_reference_shot"
  },
  "routes": [
    {
      "route_id": "route-main",
      "video_ids": ["EP01-S01"]
    }
  ],
  "videos": [
    {
      "video_id": "EP01-S01",
      "visible_name": "EP01-S01",
      "source": "EP01-S01.mp4",
      "source_media_ref": "private-master-ref",
      "source_media_version": "master-v1",
      "render_revision": 1,
      "duration_ms": 10000,
      "width": 1920,
      "height": 1080,
      "output_name": "EP01-S01-subtitled.mp4",
      "title_card": {
        "mode": "black_screen",
        "text": "游戏标题",
        "translation": "",
        "title_source": "游戏企划.游戏名称",
        "duration_ms": 3000,
        "poster_frame_ms": 1500,
        "position": {"alignment": 5, "margin_l": 120, "margin_r": 120, "margin_v": 80, "text_bbox": {"x1": 480, "y1": 390, "x2": 1440, "y2": 690}}
      },
      "segments": [
        {
          "segment_id": "segment-01",
          "source": "segment-01.mp4",
          "duration_ms": 10000,
          "concat_offset_ms": 0
        }
      ],
      "dialogue_source_lines": [],
      "events": []
    }
  ],
  "worldview_contexts": [
    {
      "entry_video_id": "EP01-S01",
      "entry_episode_id": "EP01",
      "route_ids": ["route-main"],
      "topology_evidence": "唯一入口指向EP01",
      "world_rule_source": "游戏企划.游戏世界观",
      "episode_context_source": "EP01.分集剧本.完整剧本",
      "audience_prior_knowledge": "项目直接从EP01开始，无前置剧情",
      "world_rule_text": "异能者一旦暴露就会遭到秘密追捕",
      "episode_context_text": "一份港区情报疑遭泄露，沈夜被请来裁定责任",
      "episode_premise_text": "一张用来避开巡逻的换岗表泄露了，沈夜受托查明原因",
      "opening_visual_evidence": "入口视频开场显示拆封纸袋、换岗表及三人争执",
      "causal_bridge_text": "异能者被迫进入地下帮派求生，该帮派依靠秘密车队活动",
      "causal_bridge_source": "游戏企划.游戏世界观 + 铁锚帮资产描述",
      "causal_bridge_verified": true,
      "frozen_input_acknowledged": true,
      "upstream_regeneration_requested": false,
      "zero_context_check": true,
      "introduced_names": ["镜城", "沈夜"],
      "unexplained_terms": []
    }
  ],
  "route_first_appearances": []
}
```

用户不生成世界观字幕时，`worldview_contexts`使用空数组。生成时，每个独立入口至少有一条记录，用来证明字幕同时继承了剧情拓扑、入口第一集和企划世界规则；它仍是私有执行信息，不写回业务字段。

## 计划验证

运行：

```text
python3 scripts/validate_subtitle_plan.py <plan.json>
```

验证失败时先修复计划，不进入渲染。

## ASS 生成

运行：

```text
python3 scripts/build_ass_subtitles.py <plan.json> --output-dir <private-output-dir>
```

脚本为每个视频生成一个ASS文件。它不修改视频。

事件约定：

- `alignment`使用ASS数字键盘方位：2为下中，8为上中，4为左中，6为右中。
- `margin_l`、`margin_r`、`margin_v`使用像素。
- 对话和世界观使用普通文本。
- 人物介绍可通过`vertical_text`直接提供竖排文本；缺失时脚本把姓名与身份按字符换行。
- 现有空镜标题使用 `kind: title`、`title_mode: existing_empty_shot`，并记录标题来源、空镜／无人／无对白证据和海报帧。黑屏标题使用 `video.title_card`，由渲染器生成并前置拼接。
- 文本中的换行由`\N`表示。
- 每个事件必须提供完整的 `text_bbox`。人物介绍还必须提供 `character_bbox`、`face_bbox`、`character_side`、`first_clear_visible_ms` 和 `first_clear_frame`。
- 使用显式 `x/y` 时，ASS `alignment` 对应的锚点必须落在 `text_bbox` 的相应边或中心：4/5/6 的 `y` 是整块文字的垂直中心，不是首字位置。计划锚点与文字框矛盾时验证失败。
- 每个对话事件必须提供 `source_line_id`、`source_segment_id`、`segment_local_start_ms`、`segment_local_end_ms`、`concat_offset_ms`、`audio_start_evidence` 和 `audio_end_evidence`。
- 对话全局时间必须严格等于片段本地时间加该片段的真实拼接偏移。

## 对话时间轴

不得根据台词顺序、建议镜头时长、片段平均分配或人工目测均匀铺字幕。

1. 先用 `ffprobe` 取得每个原始 segment 的实际时长，计算精确 `concat_offset_ms`。
2. 逐个 segment 读取音频。优先使用可返回词级或句级时间戳的语音识别；不可用时结合波形、静音检测和反复试听定位每句话的第一音节与最后音节。
3. 在 segment 本地时间内完成台词对齐，再加该 segment 的偏移得到完整剪辑时间；禁止直接在合片总时间轴上按比例猜测。
4. 建立 `dialogue_source_lines` 清单。最终视频中实际说出的每条正式台词状态记为 `spoken` 并关联唯一 `event_id`；确认未说出的正式台词记为 `not_spoken_in_final` 并提供证据。
5. 每个对话事件必须反向关联唯一正式台词。台词数量、文字、说话人和事件一一对账后才可渲染。

## 视频渲染路径

验证计划后，使用随 Skill 交付的确定性执行器：

```text
python3 scripts/render_subtitle_plan.py <plan.json> --output-dir <private-output-dir> [--font-file <font-file>]
```

该脚本先调用计划验证和 ASS 生成，再逐视频执行 FFmpeg 烧录；黑屏标题卡会被真实生成并拼到入口视频前。最后校验宽高、预期时长、非空输出，并打印 `nextplay.video-subtitles.render.v1` JSON 回执。`build_ass_subtitles.py` 只生成字幕轨，不能单独作为完成凭证。

只有运行环境提供的其他渲染能力能同样证明事件、字体、坐标、音频、时长和输出文件全部满足本合同，才允许替换该执行器；必须保存等价回执。音频复制不兼容时，使用无损或高质量音频编码并记录原因。

不要原地覆盖输入。所有中间文件和证据必须留在非 Canvas 私有工作区；不能通过把它们放进 Canvas 子目录来规避此规则。
不得使用 `drawtext` 的 `box=1`、ASS `BorderStyle=3` 或任何矩形底纹。默认
`background_mode` 必须为 `none`，ASS 背景色完全透明、阴影为0，只保留细描边。

## 结构检查

- 输出文件存在且可解码。
- 画面比例、宽高、帧率和总时长符合输入。
- 音频轨仍存在，声画同步没有漂移。
- 黑屏标题卡使总时长精确增加计划时长，原片音频整体后移；空镜标题不改变总时长。
- 每个计划事件均落在视频持续时间内。
- 每个文字框完整位于5%至95%安全区，不能只检查锚点。
- 世界观事件只位于对应入口视频0至5000毫秒。
- `generated_reference_shot`或`existing_exclusive_segment`模式下，世界观事件不与人物介绍或对话事件重叠；`existing_whitespace`模式允许时间重叠，但各字幕完整文字框不得相交。
- 人物介绍事件具有路线适用范围和首次出场记录。
- 每个 `spoken` 台词恰好关联一个对话事件，每个对话事件恰好关联一个正式台词。
- 每个对话事件的全局起止时间与 `segment_local_* + concat_offset_ms` 完全一致。

## 视觉检查

抽取每个字幕事件的开始、中间和结束附近帧，检查：

- 字体正确、无缺字、方框、乱码或错误回退。
- 文本清晰，透明背景与细描边足以应对所选留白区域。
- 世界观文字位于经多帧验证的稳定留白，不覆盖空镜主体；双语世界规则和本集前情默认顺序显示，不同时堆成四行。
- 默认背景完全透明，不存在黑条、色块、渐变、纹理或矩形底纹。
- 不遮挡人脸、眼睛、手部关键动作、关键道具和产品UI。
- 不越出安全区，不贴边，不被裁切。
- 双语行序和字号正确。
- 竖排姓名与身份顺序正确。
- 中英或其他双语模式的人物姓名与身份译文存在，并与正确的中文人物介绍成组。
- 人物介绍开始帧中本人已清晰出现；介绍文字与人物位于画面同一侧且距离足以建立对应关系。
- 人物姓名通过至少两个独立身份锚点与画面人物匹配，不得把左右两人的姓名或身份对调。
- 抽取标题 `poster_frame_ms` 对应帧；标题清晰、构图完整、来源正确。空镜标题的开始、中点、结束均无人且无对白，黑屏标题后第一帧与原片连续。

位置失败只调整对应事件，不重写无关字幕。

对每个事件至少抽取开始后100毫秒、中点和结束前100毫秒三帧。人物介绍额外抽取
`first_clear_visible_ms` 对应帧；对话额外试听事件开始前后各300毫秒，确认第一音节和最后音节没有明显提前或滞后。

## 内容检查

- 正式台词与分集剧本一致。
- 对话事件的渲染文本只含台词正文；中文和译文都不含说话人姓名、冒号、动作、舞台或情景说明。
- 所有最终视频中实际说出的正式台词均有字幕；不得因为 segment 同时承担世界观或人物介绍而漏掉该段对话字幕。
- 说话人与字幕一致。
- 翻译术语和称谓全项目一致。
- 紧密接话直接衔接，无淡入淡出。
- 世界观说明同时包含理解第一集所需的世界根本矛盾和本集开场事件，不是整部作品简介。
- 两句之间具有可追溯到现有企划、资产、分集或视频的真实因果桥，不是两个并列信息。
- “不站队”“卷入危机”等抽象词不能代替具体身份、事件或任务。
- 默认只引入地点和主角两个专名；配角、组织、物品和行业术语未在画面中介绍前不得塞入开场字幕。
- 前5秒总字量默认不超过36个汉字；超出时删减信息或走空镜询问，不提高闪屏速度。
- 每个世界观上下文必须确认上游已冻结，且`upstream_regeneration_requested`为`false`；字幕计划不得携带重写或重做上游的动作。
- 双句组合必须记录`causal_bridge_text`、`causal_bridge_source`并通过验证；找不到桥时不得伪造通过，应返回 Ask User 分流。
- 世界观说明不泄露第一集后段事件、分支结果或后续真相。
- 世界观说明的入口、第一集和观众知识边界可追溯到剧情拓扑与正式分集内容。
- 每条可达路线人物介绍恰好在首次真人出场触发。
- 人物介绍不能早于本人首次清晰帧，不能仅凭角色将在本 segment 出现而从片头提前显示。
- 生成世界观空镜时必须记录入口视频真实参考帧或同制作链资产、参考生视频方式和跨切点风格连续性证据；纯文字生成且无法证明画风连续时验收失败。

## 完成门禁

仅当所有目标视频版本同时通过结构、视觉和内容检查时：

1. 把内部状态改为`completed`。
2. 按`delivery-and-versioning.md`把烧录媒体关联到原`video_id`，保持用户可见名称不变，并切换活动媒体版本。
3. 只以顶层`分镜视频`返回同一业务项的状态和文件/URL。
4. 放行封面生成。

部分成功、待复检或失败都保持`in_progress`或`failed`，继续阻塞封面。
