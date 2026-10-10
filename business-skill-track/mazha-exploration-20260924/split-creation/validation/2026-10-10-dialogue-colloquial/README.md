# 2026-10-10 对白口语实例与更新核对

用户批准：少加规则，追加已确认的口语实例，善用“就”；核对最近 Skill 更新。

## 当前资源与改动

线上蚂蚱测试探索预设仍绑定 `mazha-screenplay-1008`（e27c0130-be87-4756-9652-0e2cad2f31c2）；截图中的旧 `mazha-screenwriting-1008` 不作本次更新目标。

本次仅在当前对白参考追加4组口语改写、6个“就”字例句及避免套句提醒。未增加新创作/复写阶段。发现共享 CLI 更新后，另修 cli-handoff 和 live-creation 的保存参数为 `script set --text <UTF-8文件路径|->`，纯文本保留真实换行，不包 JSON。

Studio 原资源保存17:15（对白）与17:18（接口说明），重新下载最终9个有效资源文件核对。本次线上只变 dialogue / cli-handoff / live-creation，另外6个文件原字节保留；当前9文件已同步本个人源目录。SKILL.md 的4行本轮范围与展示来自前端02已在线保存的迁移，本次只是同步留底，没有修改线上入口。

## 最近更新核对

前端02迁移的最新版留底：`/Users/automaticgrasshopper/Documents/ChatGPT/影视游戏本地前端实验/frontend/docs/lab-validation/2026-10-10-creation-plan/policy-migration/`。已读 before/after 与 README，并得到前端02确认未继续编辑这三套 Skill。

- 大纲：新增 materials-and-scope 与 research-before-creation，入口先判断已有材料、用户范围和真正缺口；保留原稿，导入/派生/创作分开。点名作品须有实际阅读的直接相关来源，失败或无关材料不能替代；仍不足则说明缺口停止，明确允许跳过才推进。
- 编剧：入口补本轮范围与展示，导入/复用与新写剧本区分；仍直接编剧、逐段真实保存。
- 形象：更新原图用途、明确改图授权与逐图保存确认；source参考及PNG保持。
- SP：承接本轮范围、停止点、能力分派、请求事实和公开创作阶段。前端发送用户原话与附件定位事实，规则不再由前端拼入。

当前绑定共享CLI最新16:14，来源nextplay-cli-389e40a.zip。对昨日20:03下载包比较，有效代码/文档变更为 nextplay.bin、SKILL.md、assets、asset-materials、screenplay、shot-video：

1. 新增 asset apply 原子整批新增/更新，整批最终状态检查交叉引用，单项 add/update 仍可用。
2. script set 改必填 --text 纯文本文件/stdin，旧JSON --input不再列入SetScript选项。
3. 共享图片规则改同时发出批量任务、全部返回后整批Slot交付；音色按候选/详情/绑定三轮并行。
4. 共享编剧参考把阶段进度绑到实际工作稿与调用的www.summary，格式问题单独修复；自有直接编剧覆盖其五阶段流程，未引入这些共享写作步骤。
5. 分镜视频完成改Summary交付；project check新增PLAYBACK_DEFAULT_STALE说明，由下次路线修改重算。

共享routes.md与当前共享路线规划正文未变化。我们复制的拓扑两篇子参考逐字一致；主参考只有已有包装、优先级说明和相对链接替换。共享资源均只读。

## 核验边界

本次做线上重开、下载逐文件比较、字符串及链接检查，没有运行新故事/媒体生成。不能据此宣称实际成稿质量已验证。原迁移中的 perspective 来源不一致仍是另项问题。共享CLI包只读取文档/源码，未读取runtime.env、未执行项目写入。

口气示例参考此前已检索的公开“就”字用法：https://www.uv.es/confucio/revista21/html/files/assets/basic-html/page30.html 。例句为本次拟写，不复制作品台词。

页面证据与原包前后正文：`/Users/automaticgrasshopper/Documents/ChatGPT/影视游戏本地前端实验/validation/2026-10-10-dialogue-colloquial/`。
