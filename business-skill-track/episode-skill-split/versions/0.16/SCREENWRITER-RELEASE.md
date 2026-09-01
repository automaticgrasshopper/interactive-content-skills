# `episode-screenwriter-biz` 0.16 研发记录

本文只记录仓库版本关系，不属于 Skill 运行文件，不上传到 Skill 后台。

## 版本关系

- 当前研发版本：`episode-screenwriter-biz/0.16`
- 内容起点：线上 `episode-screenwriter-biz-tiantian` 稳定副本
- 仓库对应基线：`episode-screenwriter-biz/0.12`（自身由 0.11 演进）

## 版本号边界

- 版本号仅由 Git、版本目录和本说明维护。
- 线上 Skill 的名称、slug、主说明、参考资料、脚本、运行输出及正式剧本合同均不展示研发版号。
- Skill 目录不保存版本 manifest；打包上传时也不包含本说明。

## 当前调整

- 运行文件不得出现发布版号、带版号的 Skill 身份、`skill_version`字段或发布版本常量。
- 合同自身的 `contract_version`、项目路线的 `route_version` 等业务字段不属于研发版号，继续保留。
- 不合入 0.13—0.15 的新增创作资料或脚本能力，避免稳定基线被混入其他版本能力。
