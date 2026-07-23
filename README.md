# episode-generator Skill

本仓库独立维护 `episode-generator` Skill。可安装目录为
`episode-generator/`，其中只保留 Skill 运行所需的指令、references、
scripts 和 agents 元数据。

## 维护边界

- 本仓库不依赖互动节奏平台的前端、后端、项目数据或运行记录。
- 互动节奏平台不应 import、读取或按版本跟随本仓库中的文件。
- 两边的实验结论只通过中性 `experiment-report` 交换；采纳结论时分别在各自仓库重新实现和验证。
- Skill 的版本、测试、提交、tag 和发布均在本仓库独立完成。

## 版本

正式版本使用 Git tag。Skill 声明版本位于
`episode-generator/reference-manifest.json`，发布时必须与 tag 一致。

历史来源与提取校验见 `PROVENANCE.md`。
