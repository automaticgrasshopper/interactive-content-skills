# 分集 Skill 拆分版本

本目录保存从 `episode-generator-biz` 拆分出的两项业务 Skill 及其版本历史：

- `episode-route-planner-biz/0.01`：生成、比较并冻结互动剧情拓扑，不写分集正文。
- `episode-screenwriter-biz/0.11`：读取已验收的冻结拓扑，一次只为一个指定节点完成分集剧本，不改写路线。

当前活动版本由 `field-ownership.json` 指定。

## 已确认基线

`episode-route-planner-biz/0.01` 已于 2026-08-28 确认为流程图拓扑最终版。后续默认保持该版本，不再调整拓扑生成与选择逻辑；只有明确提出新需求或修复已确认问题时才另开版本。

`episode-screenwriter-biz/0.11` 已于 2026-08-28 经实际使用确认可用，整体效果良好。后续写作 Skill 的调整以此版本为基线；历史版本保留用于比较和回查。

这是一项仓库版本说明，不属于 Skill 运行指令，不应上传为线上 Skill 文件。
