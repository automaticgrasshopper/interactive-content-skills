# 0814 三阶段分集 Skill：第七步发布验收

## 范围

- 已完成基线冻结、能力拆分、交接合同、三个本地 Skill、自动续跑规则、本地隔离验证、Maxwell 上传和测试预设换绑。
- 线上`蚂蚱-分集规划师-0813工程测试`本体未修改、未替换、未删除；只从`蚂蚱的字幕测试`预设中取消绑定。

## 基线保护

- 仓库基线：`b0952cdb6931f80ec174bf7a5c408c6eb9fe26bb`
- 原Skill目录：`business-skill-track/episode-generator-biz/0.46`
- 原目录Git diff：空
- 固定文件和Git tree指纹见`baseline.json`。

## 新Skill

1. `versions/0.01/episode-branch-planner-biz`
2. `versions/0.01/episode-screenwriter-biz`
3. `versions/0.01/episode-script-validator-biz`

## 阶段所有权

- 分支规划师不含Enhancer和正式业务组装脚本。
- 剧本创作师不含Enhancer和正式业务组装脚本。
- 剧本校验师独占Enhancer、正式业务组装器和`verify_deliverable.py`。
- 剧本校验师复制的全部原0.46 Reference和业务脚本与源文件SHA-256一致；只新增三阶段交接脚本与调度说明。

## 交接验证

- `planning-handoff.json`绑定冻结故事、拓扑、情绪脊、路线时长和全部梗概。
- `writing-handoff.json`绑定当前规划交接、逐集适配材料、写作输入、Screenwriter原稿和原稿PASS回执。
- 任一绑定文件被修改、删除或替换，下游验证失败。
- 非法越界路径被拒绝。
- `character-introductions.json`允许在第三阶段按原流程填写，不会错误破坏规划交接。

## 测试结果

标准库单元测试共11项，全部PASS：

- Skill frontmatter、Reference、脚本和UI元数据完整性
- 冻结基线哈希
- 三份交接实现一致性
- 阶段脚本所有权
- 原业务校验器与Reference逐字一致
- 完整规划→写作交接
- 原稿篡改拦截
- 拓扑篡改拦截
- 缺失产物拦截
- 路径越界拦截及首次出场合法后填

使用新剧本校验师内的原业务验证器读取既有13集正式结果，输出：

```text
STRUCTURE_PASS
NOT_A_COMPLETION_ATTESTATION
```

这证明九字段业务结构兼容，同时继续区分结构通过与最终完成证明。

官方`quick_validate.py`所在运行环境缺少其自身的`PyYAML`依赖；未安装系统依赖。已使用Ruby标准YAML解析器和本项目测试执行同等frontmatter约束，三个Skill均通过。

## Maxwell发布结果

- 业务ID：`ad3d5c4b-c7c9-4ed3-b15d-4f3556520263`
- 发布时间：`2026-08-14T08:56:54Z`
- 已导入`蚂蚱-分支规划师-0814工程测试`（`episode-branch-planner-biz`）。
- 已导入`蚂蚱-剧本创作师-0814工程测试`（`episode-screenwriter-biz`）。
- 已导入`蚂蚱-剧本校验师-0814工程测试`（`episode-script-validator-biz`）。
- 测试预设：`蚂蚱的字幕测试`（`49687b5d-6a04-49ed-a274-a8d1ce8afa57`）。
- 保存后刷新读回：三个0814 Skill均为启用，旧0813 Skill为停用。

## 尚未执行

- NextPlay前后台端到端生成与中断恢复测试

以上属于第八步。
