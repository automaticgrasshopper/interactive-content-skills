# `episode-route-planner-biz` 0.08 发布关系

本文只记录仓库版本和线上部署关系，不属于 Skill 运行文件，不上传到 Skill 后台。

## 版本身份

- Git 留档版本：`episode-route-planner-biz/0.08`
- 仓库目录：`versions/0.08/episode-route-planner-biz/`
- 保留可靠基线：`episode-route-planner-biz/0.01`
- 正式线上名称：`蚂蚱-分支设计师0831`
- 正式线上 slug：`episode-route-planner-biz`

## 测试到正式的关系

- 0.08 在线上回归期间曾临时使用名称`蚂蚱-分支-0901新测试`和 slug `episode-route-designer-biz`，目的是与 0.01 正式基线并存测试。
- 短分支连续两次通过、开放长分支通过后，0.08 的 12 个运行文件已原位覆盖到正式`蚂蚱-分支设计师0831 / episode-route-planner-biz`。
- `【线上环境】影游Agent工程测试`继续引用原正式 Skill ID；`蚂蚱的测试`也已改为引用该正式 Skill。
- 后台临时`episode-route-designer-biz`已在确认无 Preset 引用后删除。它不是另一条产品线，其实现就是本目录保存的`episode-route-planner-biz/0.08`。

## 版本号边界

- 版本号由 Git、版本目录和本说明维护。
- 线上 Skill 的名称、slug、主说明、脚本运行输出及正式路线合同不展示 0.08。
- 后续修改从本目录或 Git 提交追溯，不恢复临时 designer slug；若需要并行灰度，应另建临时入口，但最终仍归档到 planner 的新版本目录。

## 0.08 验收要点

- 用户说的剧情节点、集或段只统计剧情卡；独立选择点另计，选项只是边。
- 用户已唯一确定形状时，只生成一版拓扑并做一次机械验收，不进行第二版、匿名比较或内容复检。
- 开放形状仍生成两版真正异构拓扑；第二版一落盘即比较图形指纹，同指纹只退回重做第二版，不进入总验收。
- 未指定数量时保持自然发散、非对称拓扑和由人物情绪脊驱动的选择。
