# 分集 Skill 拆分版本

本目录保存从 `episode-generator-biz` 拆分出的两项业务 Skill 及其版本历史：

- `episode-route-planner-biz/0.08`：以用户明确数量和形状为第一约束；固定形状单版验收，开放形状生成真正异构的两版路线，不写分集正文。
- `episode-screenwriter-biz/0.16`：以线上稳定副本（仓库内容身份为 0.12）为唯一内容基线，一次只为一个指定节点完成或追改分集剧本；Skill 包自身不感知研发版本。

当前活动版本由 `field-ownership.json` 指定。

## 当前活动版本

`episode-route-planner-biz/0.08` 将剧情卡、独立选择点和选项边分开计数，逐项核对用户冻结数量；固定形状时只生成一版并做一次机械验收，开放形状才生成两版并在总验收前阻止相同图形指纹。

`episode-screenwriter-biz/0.16` 保持线上 `episode-screenwriter-biz-tiantian` 稳定副本的运行能力和文件边界，只移除 Skill 内部的版本 manifest、发布版号字段和写死的上游发布版号。版本关系只由 Git、版本目录及 Skill 外部发布记录维护。

## 保留基线

- `episode-route-planner-biz/0.01`：原拓扑最终基线，保留用于比较和回查。
- `episode-route-planner-biz/0.02`：双因果闭环基线，保留用于比较和回查。
- `episode-route-planner-biz/0.03`：中文阶段入口与干净上下文基线，保留用于比较和回查。
- `episode-screenwriter-biz/0.11`：原分集写作基线，保留用于比较和回查。
- `episode-screenwriter-biz/0.12`：双因果表演与成稿后对话追改基线，保留用于比较和回查。
- `episode-screenwriter-biz/0.13`：真人短剧对白参照基线，保留用于比较和回查。

这是一项仓库版本说明，不属于 Skill 运行指令，不应上传为线上 Skill 文件。
