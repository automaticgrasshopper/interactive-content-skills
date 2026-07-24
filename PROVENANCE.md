# Provenance

统一 Skill 仓的首个基线从以下已提交内容提取：

- 来源仓库：`interactive-drama-lab`
- 来源提交：`d12249b6e7dcb7f12a862fed5d2970e875597b86`
- 来源路径：`skill/`
- 来源 Git tree：`da927700a6e1edd7d4a7c78f626729e804df0f20`
- 历史提取提交：`5ee1e68459c81188997ef505d861612f07d4ca4e`
- 正式 Skill 数：11
- 正式文件数：33

提取完成时，独立仓根 tree 与来源仓库 `skill/` tree 完全一致。之后只把
11 个 Skill 整体移动到仓库级 `skills/` 目录，没有修改任何 Skill 正文、
reference、script 或 agents 元数据。

平台目录中被 `.gitignore` 排除的 `.bak-*` 临时副本、Skill 版本备份和运行
缓存不属于正式 Skill 基线，也没有进入本仓库。

上述信息只用于历史追溯，不构成与互动节奏平台的运行时依赖、版本跟随或同步关系。
