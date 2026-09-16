# NexPlay 后期 Skills

这里独立维护 NexPlay 两份业务后期 skill，与剧集规划、编剧 skill 分开管理。

| 目录 | Maxwell Skill ID | 当前修订 |
|---|---|---|
| `video-editing-subtitles-music-biz` | `504c21de-f3e4-4ce0-bb72-b5e73e87fbe6` | `interaction-chain-20260916-r25` |
| `video-editing-subtitles-music-test-biz` | `5e20600a-a4cc-4414-81d6-a5d31cd5fe6e` | `interaction-chain-20260916-r24` |

每个目录包含完整的 SKILL.md 与 references，可独立对照 Maxwell 发布内容。Git 历史保存后续修订，不把运行项目、凭据、接口响应或测试媒体提交到本目录。

## r24 变更

- 世界观引入按宏大时代／世界背景、局部特殊设定、生活化事件分类；仅宏大背景默认中英双语，用户语言要求优先。
- 局部设定提炼设定与问题／悬念；生活化引入提炼事件与已有悬念，不编造剧情。
- 在左右上角附近选择避开主体的留白，组内始终视觉左对齐。
- 按每行实际尺寸换算中心坐标，右上按最长行确定整组左边缘；完整字形及描边必须在 5%–95% 安全区内。
- 统一旧版世界观分轨说明，保留逐显示行独立可编辑轨道。

## 维护与验证

今后在本目录维护并同步提交至本仓库。更新 Maxwell 时先读取远端保留无关字段，上传后逐文件读回比对，再记录发布结果；未经用户授权不运行实际项目测试。

本次结构校验通过。发布后的文件一致性结果见 release.json；未执行播放器实测，不将规则更新当作实际无溢出证明。

2026-09-16：原 timeline 测试资源原地更名为 `video-editing-subtitles-music-biz`，保留 UUID `504c21de-f3e4-4ce0-bb72-b5e73e87fbe6`；规则仍为 r24。此次更名未挂载主预设，正式团队资源仍需走 PR 发布。

r25：按镜头效果与戏剧功能剪辑，允许完整删去不承担必要功能的对白；保留句子完整、问答指代、剧情与情绪衔接。入口、剪辑、对白、字幕和验收五处规则统一；保留原 UUID。正式 PR：https://github.com/world-sim-dev/nextplay-fe/pull/27 。另一测试资源仍保留 r24。
