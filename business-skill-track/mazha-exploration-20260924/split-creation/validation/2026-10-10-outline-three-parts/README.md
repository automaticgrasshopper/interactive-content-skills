# 大纲三段与同一短故事：2026-10-10

用户在「影视游戏新交互核心02」要求与「配合skill优化02」协作，改完展示，本轮不测试。仅修改自有实验SP和大纲Skill规则；没有运行用户项目、修改既有故事或媒体，没有修改共享CLI、主预设、正式前后端或创建新Maxwell资源。前端视角联动由前端02单独负责。

## 完成的行为约定

- 先形成logline，再直接由它写通完整短故事；从同一故事提炼高潮前的前半段预览和玩家介绍。预览在自然叙事停顿处以“……”结束，不按字数截半；logline简练具体，不强制省略号结尾。
- 大纲三段依次为logline、短故事预览、玩家介绍。第三人称以“玩家需要扮演……”开头，第一人称以“你将扮演……”开头，后文沿同一种角色处境与行动句法。不给结局菜单、取舍算法、免责声明或“本故事”等创作说明，事实边界内部遵守。
- 先真实留存并读回完整短故事和提案关联；三段齐备后一次保存并读回，再发原大纲卡，不先投影仅logline半成品，不新增确认关卡。
- 完整短故事是确认前工作区材料，不启动route generate、不写planning/state，不公开【短故事】/【核心故事】/【本集剧情】全文标记。该前置任务presentation=progress，只播报真实形成进展。
- 确认后读对应全文，空图首次story-core提交复用原文；不从logline另编同一故事。用户改稿/既有剧情变化只同步受影响部分；旧稿缺失时从当前确认材料补齐一次并说明来源，不假装找到旧全文。

## 真实字段与留存合同

当前绑定CLI文档及源码schema只有premise.logline、premise.description、play.player、play.perspective；无独立story或player_role字段。

- premise.logline：第一段。
- premise.description：第二段预览＋两个真实换行＋第三段玩家介绍；JSON提交时正确转义换行。
- play.player：同一第三段介绍。
- play.perspective：first/third，保留实际选择。
- 完整story-core.md及outline-proposal.md：当前Thread工作区按实际项目/request分目录留存；proposal记录准确三段、视角、来源和真实全文定位。没有信封时用真实版本标识，不捏造ID。它们不冒充项目字段或已提交规划。

最新用户保存story.outline和明确改选的settings.perspective优先，同步CLI play.player/play.perspective和提案关联，旧outline.play不能反向覆盖新设置。CLI script context源码直接复制play.perspective/player到context.settings，不能据此声称edition后端投影也已验证；本轮没有改adapter。

## 保存范围与证据

SP原资源：fff75383-8b7d-40e4-a46e-45208a52a5a1；Skill原资源：7de81a35-b816-46f7-b68e-f50392dc5927；slug mazha-outline-route-1008；当前名称「蚂蚱-构思创意大纲流程图-1008」，名称、ID、绑定均保留。二者仍仅引用实验预设8bf0ce65-3d52-4819-97d7-9afbb5751203。

线上基线来自本轮Studio实际下载17:28的27文件包和live SP，包含17:22轻量调研、工具用途播报，未使用policy-migration旧after覆盖。原资源保存17:38后重新下载全27文件，全部与after一致；仅8文件变化、19文件原字节不变。SP保存后刷新、重新选中、读取源码与after完全一致，哈希见remote-verification.json。

改动Skill文件：SKILL.md，以及references/creative-entry.md、cli-handoff.md、materials-and-scope.md、continuation-handoff.md、story-development.md、cli-topology.md、interaction.md。后面几份只修复“确认后重写短故事”或“两段”旧入口冲突；不改共享拓扑源，不新增阶段工程或脚本。

原稿、改后稿、完整线上读回、diff、截图和逐文件哈希位于本目录。没有运行测试、构建、生成或项目写入；读回只证明配置保存一致，不宣称实际创作效果已验收。个人源目录同步该两资源的当前完整版本以防旧稿回滚，其他Skill未改。
