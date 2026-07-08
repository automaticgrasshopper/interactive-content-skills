# 故事板输出契约（可选 JSON schema）

当调用者需要结构化产物（供程序/H5 消费）时，用这份 schema。字段名固定、英文 key，值可中文。没有此需求时用 SKILL.md 的 Markdown 输出即可。

## 顶层结构

```json
{
  "shared_creative_direction": {
    "title": "剧集/项目名",
    "genre": "类型",
    "target_medium": "interactive_cinematic_game | premium_tv_drama | short_drama | anime_layout | game_cutscene | commercial_film",
    "palette": "全片主色板（可复用分镜工作台的 hex 组）",
    "style": "美术方向一句话，全片统一",
    "episode_duration_sec": 0,
    "duration_rationale": "为什么是这个时长",
    "assumptions": ["输入缺失时补的假设，逐条列出"]
  },
  "characters": [
    {"id": "char_001", "name": "", "identity": "年龄/性别/体型", "hair": "", "outfit": "", "accessories": "", "face_baseline": "", "objective": "本集目标", "anchor_image": "有则填参考图 URL/占位"}
  ],
  "scenes": [
    {"id": "scene_001", "name": "", "time": "日/夜", "inout": "内/外", "layout": "空间地理：门/窗/主陈设相对位置", "impassable": ["桌","墙"], "walkable": "可行走路径描述", "light": "", "key_props": []}
  ],
  "episode_storyboard": {
    "rhythm_overview": {"beat_order": ["铺垫","压力","转折","决定","揭示"], "power_shift": "", "emotion_arc": ""},
    "frames": [
      {
        "frame_no": 1,
        "duration_sec": 3,
        "scene_id": "scene_001",
        "char_ids": ["char_001"],
        "size": "景别",
        "lens": "焦段/镜头感",
        "camera_move": "固定/极简运动",
        "blocking": "调度：谁在画框哪、轴线哪侧",
        "eyeline": "视线关系",
        "action": "动作",
        "dialogue": "台词或『有意沉默』",
        "emotion": "情绪推进",
        "continuity": "与上一帧空间关系（同轴延续/反打/切近/首帧）",
        "audio": "音效/音调"
      }
    ]
  },
  "shot_groups": [
    {
      "group_id": "g1",
      "source_frames": [1, 2],
      "char_ids": ["char_001"],
      "scene_id": "scene_001",
      "total_duration_sec": 6,
      "continuity_value": "为什么这几帧能合成一组（运动路径/对话交换/物件因果/情绪节拍/视线）",
      "edit_rhythm": {
        "dramatic_function": "单一戏剧功能",
        "info_density": "低/中/高",
        "cut_trigger": "剪切触发点",
        "performance_in_out": "表演起止状态",
        "hold_budget": "允许停顿",
        "generation_risk": "低/中/高 + 原因（穿门槛/长行走/多房间漂移/多移动演员/大覆盖变化/关键人物可能消失）"
      },
      "ref_to_video_prompt": "英文或中文视频提示词：参考资产角色 + 连续性锚点 + 运动 + 台词/音频意图 + 负向限制；命名人物跨房间移动含单实例锚点；门/电梯/车门含首末帧或剪到结果态。"
    }
  ],
  "visual_board_prompt": "那张 16:9 网格制作板本身的生成提示词（见 SKILL.md 视觉策划板规则）"
}
```

## 校验要点

- `shot_groups[].source_frames` 里的编号必须都存在于 `episode_storyboard.frames`。
- 每个 `shot_group.total_duration_sec` ≤ 视频模型上限（默认 15）。
- 每帧必有 `duration_sec / scene_id / char_ids / blocking / dialogue(或有意沉默) / continuity`。
- `char_ids` / `scene_id` 必须能在顶层 `characters` / `scenes` 里找到。
