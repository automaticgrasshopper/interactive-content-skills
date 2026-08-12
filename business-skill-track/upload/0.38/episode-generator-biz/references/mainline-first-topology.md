# 主线原文先行拓扑

## 原则

`mainline-story.json/complete_story`是唯一主线事实文本。先把它切成一条有起承转合的纯直线路径，再在这条路径上扫描决定裂缝。支线长在主线节点上；支线不得先生成一篇全路线故事，再反向压缩或重写主线。

## 主线分解

创建`mainline-decomposition.json`：

```json
{
  "contract_version": "nextplay.mainline-decomposition.v1",
  "mainline_sha256": "mainline-story.json规范化SHA-256",
  "segments": [
    {
      "segment_id": "mainline-001",
      "title": "候选分集标题",
      "source_text": "冻结可读故事中的连续逐字原文"
    }
  ]
}
```

所有`source_text`必须按出现顺序、无重叠、无遗漏、无改写覆盖完整故事；切片之间只允许存在原文空白。每个切片首先按完整戏剧运动判断：建立处境、完成行动变化、形成决定或落地结果。不得按预设节点数平均切字数。

## 裂缝与主线动作

沿这些主线切片扫描决定。裂缝位于切片内部时，只能在原文边界继续拆分切片：

- 来源切片保留到决定已成立、主线行动尚未执行。
- 冻结主线原本执行的动作成为一个选项。
- 该动作及其后果从下一主线切片开头继续，仍逐字使用原文。
- 其他选项才生成新的支线。

拆分后重新运行分解门禁。不得改变原文以迁就选择形式。

## 正式映射

拓扑完成时创建`mainline-path.json`：

```json
{
  "contract_version": "nextplay.mainline-path.v1",
  "path": [
    {"segment_id":"mainline-001","episode_id":"episode-001"}
  ]
}
```

映射必须包含全部主线切片且一一对应，顺序等于`route-duration.json/mainline_path`。每个非末尾主线节点必须直接连到下一个主线节点；有选择时，至少一个选项必须指向下一个主线节点。最终主线节点必须是冻结期待结局。

全体梗概生成后，主线`episode-synopses/<episode-id>.json/synopsis`必须逐字等于对应`source_text`。只有支线节点的梗概可以从支线事实另行生成。
