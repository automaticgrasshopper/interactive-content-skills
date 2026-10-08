# 体量展示与拓扑约束 · 2026-10-08

用户通过“接续影游增量打印会话”明确转交本 Skill 优化：玩家不问时不展示自动游戏体量，问时回答；拓扑不能据 AI 自动时长或短篇档位压缩结构，明确用户要求仍保留。

修改入口及 creative-entry、story-development、graph-contract、interaction，共五个 Skill 文件；同步架构说明。未修改共享 nextplay-cli、模型、前端或旧作品。

核对共享 CLI 17:24 版本的 outline/routes 文档及本体合同：duration 支持空文本或 null；outline update 只改提交字段并保存读回；route generate start 捕获 starting-project 的非空 duration，当前 outline 事后清空不解除已捕获来源；intent.long_story=false 会减少默认结构检查。因此要求规划开始前清理已确认由 AI 自动写入的时长、无明确时长时省略 intent.duration，并默认保留完整图结构，不伪造数字绕过工程门禁。已有规划若无法解除错误捕获，则报告合同限制，不直接改状态文件或未经授权重建。

修改前实际后台编辑器的五份原文逐字等于个人仓库 HEAD 9679ef8；持久化 route.json 规则已在同一后台版本确认。2026-10-08 20:04 保存原资源 mazha-route-0924，仍为 30 文件，仅由“蚂蚱测试探索”引用。下载 mazha-route-0924 (3).zip，全部 30 内容文件与本地逐字节一致。quick_validate.py、Markdown 引用存在检查与 git diff --check 通过。

本轮为指令及真实 CLI 合同核对，没有新跑完整创作样例，不宣称模型所有情况下已遵循。后台截图：/Users/automaticgrasshopper/Documents/ChatGPT/影视游戏本地前端实验/validation/2026-10-08-skill-duration/maxwell-readback.jpg。
