# 三阶段分集 Skill 版本轨道

本目录独立维护从`episode-generator-biz`拆出的三阶段流水线，不修改原单体Skill版本轨道。

## 固定成员

- `episode-branch-planner-biz`
- `episode-screenwriter-biz`
- `episode-script-validator-biz`

三个Skill使用同一版号同步发布。任何一项交接合同或正式输出合同变化，都必须同时提升三项版号。

## 目录

- `versions/<版号>/`：开发与历史归档，每个版号包含三套完整Skill。
- `upload/<版号>/`：从对应版本机械复制的干净上传镜像，只保留平台需要的Skill文件。
- `tests/`：基线指纹、交接合同、阶段所有权和业务兼容性测试。

## 发布规则

1. 原`business-skill-track/episode-generator-biz/`不参与本轨道修改。
2. 先完成`versions/<版号>`和全部测试，再生成同版号`upload/<版号>`。
3. 上传镜像必须与版本归档逐文件一致，不包含`__pycache__`、日志、运行缓存或测试夹具。
4. Maxwell中三个显示名称可带日期，slug保持固定；新版本通过平台版本替换或重新导入管理。
5. 正式工程输出仍由剧本校验师按原`episode-generator-biz`九字段合同生成。
