# `episode-screenwriter-biz` 0.16 研发记录

本文只记录仓库版本关系，不属于 Skill 运行文件，不上传到 Skill 后台。

## 版本关系

- 当前研发版本：`episode-screenwriter-biz/0.16`
- 研发起点：`episode-screenwriter-biz/0.15`
- 可靠线上回退基线：`episode-screenwriter-biz/0.11`

## 版本号边界

- 版本号仅由 Git、版本目录和本说明维护。
- 线上 Skill 的名称、slug、主说明、参考资料、脚本、运行输出及正式剧本合同均不展示研发版号。
- Skill 目录不保存版本 manifest；打包上传时也不包含本说明。

## 当前调整

- 运行文件不得出现 `0.15`、`0.16`、带版号的 Skill 身份或 `SKILL_VERSION` 常量。
- 合同自身的 `contract_version`、项目路线的 `route_version` 等业务字段不属于研发版号，继续保留。
