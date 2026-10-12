# 恢复库音色方案验收（2026-10-12）

用户最终决定：人物生图时匹配并绑定现有库音色，首次形象展示直接提供库试听和自然中文声音类型；取消单独生一句人设台词，声音不阻塞图片确认；正式视频使用绑定声音说剧本原台词。

## 修改及同步

前端移除声音ready/音频metadata对形象确认的门槛，保留图片审核、当前选中版本、文字打字、图片特效和玩家逐张确认。有效库试听不受旧voiceGenerationTaskStatus影响，不展示旧voiceSampleLine。

个人 mazha-asset-image-direct-1008、SP、mazha-outline-route-1008 的 assets.md 与 production-workflow.md 同步新规则。均通过已登录 Maxwell Studio 修改并回读一致，未使用 CLI key。仅个人实验资源与前端分支，未改共享后端/共享Skill/实际作品。

## 验证

- 21文件158项相关 Vitest 测试全部通过；tsc -b、变更源文件 eslint、Vite生产构建通过。
- 浏览器21项断言全部通过：待审核图片无确认；图片审核通过且完整展示后，声音缺失仍可确认；旧配音任务失败不隐藏库试听；不展示旧人设短句；中文类型、声音切换；第二张完整打字并等待3999ms特效；试听播放/暂停；失效音频直接提交图片确认；恢复声音不重复审核。
- 全量1600项1590通过、10失败。修改前HEAD 59d87664临时副本对同5文件复现同10失败，属既存基线。详细标题在frontend的library-voice-baseline-failures.txt。
- Skill YAML/元数据用现有js-yaml验证通过。quick_validate因无PyYAML不可用，未安装新依赖。

## 真实库音色绑定验收

从5195本地前端新建独立项目“蚂蚱库音色绑定验收-20261012”，项目ID f1ec1440-b8dd-43bb-b6d0-0d680605c1d8。仅人物周岚，ref character-cilj0g，声音设计“酷飒御姐：成年女声，中低音，直接利落”。真实voice_tone_match候选/详情后选中“冷艳女帝”。CLI asset voice bind保存，asset inspect --include media返回exitCode=0、status=ok并读回。

```json
{"voice_id":"vl_8f86a541-05cc-406d-a753-e468a09e63eb","preview_audio_url":"https://cdn.sandcdn.com/console-uploads/v621791546998657.wav"}
```

前端人物编辑弹窗识别所选库音色“冷艳女帝”；点击试听后UI切换“暂停音色”pressed（组件由audio.onplaying设置）。没有生成图片、配音、视频、转写或提取音轨，也未写故事/路线/剧本。库示范音不宣称为周岚台词。本次验证图片确认状态使用离线fixture中的真实平台组件与内存存储；未重新执行收费生图或正式视频生成。

本次新项目保留供复查：[打开验收项目](http://127.0.0.1:5195/story-creation?story_id=f1ec1440-b8dd-43bb-b6d0-0d680605c1d8#asset-settings)。实际绑定DOM与截图、四份远端保存文本同目录。
