# 验证记录

2026-09-24，本轮只验证和同步自己的测试 Skill／主提示词，未跑收费的真实整作生成。

## 已通过

- 17 项 Python 行为测试：复杂图保留原报告；错误图仍失败；自由拓扑拒绝自发循环；显式循环出口／回边与死循环检查；专家待续不冒充结局；真实单换行固定剧本格式；底稿绑定与整稿验收；陈旧输入拒绝且不覆盖先前成功产物；缺失互动 schema 拒绝。
- `graph_check.py` 与原可用来源字节一致，复杂图 rich_fixture 的 PASS、深度、woven、持续展开与阶梯报告一致。
- `skill-creator/scripts/quick_validate.py`：Skill is valid。校验依赖 PyYAML 仅安装到 /private/tmp/mazha-skill-validator，不改项目依赖。
- 全部 Markdown 相对链接有效，包内 28 个文件（入口1、引用18、脚本9），不带测试缓存。
- 独立只读前向模拟：全自动充分展开南方犯罪故事；专家续写显式调查循环。发现互动投影缺口已修，新增相应测试。
- 读现有前端标签解析，保留【主标签】【副标签】【创意词】传输标记；界面仍只显示词和颜色。

## 不把这些当作已验证

- 模型是否在真实用户一句话下完整执行全部工序，内容质量和总耗时。
- 搜索是否每次被真实调用；提示词规定必须搜，工具运行仍需查实际日志。
- CLI 实际保存循环、播放器重复播放，以及条件解锁／变量玩法。
- 专家创作权移交动画实际出现与展示队列同步。

## 运行命令

```sh
python3 -m unittest discover -s business-skill-track/mazha-exploration-20260924/integrated-creation/tests -v
/private/tmp/mazha-skill-validator/bin/python /Users/automaticgrasshopper/.codex/skills/.system/skill-creator/scripts/quick_validate.py business-skill-track/mazha-exploration-20260924/integrated-creation/skills/mazha-route-0924
```

## 同步

Studio ZIP 导入识别为现有 slug 覆盖；风险确认界面显示仅 1 个 Preset 引用：蚂蚱测试探索。导入状态 done，列表更新时间 09-24 19:42，名称与 slug 保持。

主提示词已保存，引用范围仍为唯一测试 Preset。刷新预设后，Skill Loader 的已选项仅为新版“蚂蚱-影游创作-0924”（09-24 19:42）与 nextplay-cli；网页搜索、URL 与 API 访问均处于启用状态。未修改其权限、模型、后端或其他功能模块。
