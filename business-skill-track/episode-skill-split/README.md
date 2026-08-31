# 分集 Skill 拆分版本

本目录保存从 `episode-generator-biz` 拆分出的两项业务 Skill 及其版本历史：

- `episode-route-planner-biz/0.02`：生成、比较并冻结同时满足事实因果与人物情感因果的互动剧情拓扑，不写分集正文。
- `episode-screenwriter-biz/0.13`：读取已验收的冻结拓扑，一次只为一个指定节点完成或追改分集剧本，不改写路线。

当前活动版本由 `field-ownership.json` 指定。

## 当前活动版本

`episode-route-planner-biz/0.02` 基于已确认的 0.01 拓扑架构，只增加双因果闭环：重要行动同时由事实触发和人物赋予事实的意义导致，人物或关系变化必须实际影响后续行为；纯功能过桥节点不得硬造情绪变化。

`episode-screenwriter-biz/0.13` 基于已确认可用的 0.12，把早期 `0b32c82` 中从真人短剧提炼的自然话茬、关系语体、举证升级与关系反噬方法接入现有完整场景复写；参照只调整已有戏剧拍的表达顺序，不新增冲突、证明轮次、选项、字数或动作配额。

## 保留基线

- `episode-route-planner-biz/0.01`：原拓扑最终基线，保留用于比较和回查。
- `episode-screenwriter-biz/0.11`：原分集写作基线，保留用于比较和回查。
- `episode-screenwriter-biz/0.12`：双因果表演与成稿后对话追改基线，保留用于比较和回查。

这是一项仓库版本说明，不属于 Skill 运行指令，不应上传为线上 Skill 文件。
