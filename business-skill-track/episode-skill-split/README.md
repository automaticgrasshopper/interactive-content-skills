# 分集 Skill 拆分版本

流程图候选版本：[`0.20`](versions/0.20/ROUTE-PLANNER-RELEASE.md)，正式 slug 为 `episode-route-planner-biz`。新增持续展开、双翼交织、梯度结局强校验，以及当前画布增删节点确认和局部恢复。仓库版本更新不代表正式 Maxwell 资源已同步。

本目录保存从 `episode-generator-biz` 拆分出的两项业务 Skill 及其版本历史：

- `episode-route-planner-biz/0.20`：从完整故事切出剧集，按用户硬约束展开复杂路线；机器验图，作者负责剧情，已有画布按当前删改局部恢复。
- `episode-screenwriter-biz/0.16`：以线上稳定副本（仓库内容身份为 0.12）为唯一内容基线，一次只为一个指定节点完成或追改分集剧本；Skill 包自身不感知研发版本。

当前活动版本由 `field-ownership.json` 指定。

## 当前活动版本

`episode-route-planner-biz/0.20` 保留“一集＝一个非选择剧集节点”。非短故事默认持续开扇、双翼交织和分层结算，用户明确数量和形状优先；按当前画布确认增删、修复接缝后继续原请求，不恢复整张旧路线。

`episode-screenwriter-biz/0.16` 保持线上 `episode-screenwriter-biz-tiantian` 稳定副本的运行能力和文件边界，只移除 Skill 内部的版本 manifest、发布版号字段和写死的上游发布版号。版本关系只由 Git、版本目录及 Skill 外部发布记录维护。

## 保留基线

- `episode-route-planner-biz/0.01`：原拓扑最终基线，保留用于比较和回查。
- `episode-route-planner-biz/0.02`：双因果闭环基线，保留用于比较和回查。
- `episode-route-planner-biz/0.03`：中文阶段入口与干净上下文基线，保留用于比较和回查。
- `episode-screenwriter-biz/0.11`：原分集写作基线，保留用于比较和回查。
- `episode-screenwriter-biz/0.12`：双因果表演与成稿后对话追改基线，保留用于比较和回查。
- `episode-screenwriter-biz/0.13`：真人短剧对白参照基线，保留用于比较和回查。

这是一项仓库版本说明，不属于 Skill 运行指令，不应上传为线上 Skill 文件。
