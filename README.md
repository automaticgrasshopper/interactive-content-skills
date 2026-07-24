# 互动内容 Skills

本仓库统一维护互动影视、互动叙事和剧本生产相关的 11 个 Skill。
每个 `skills/<skill-name>/` 目录都是独立可安装的 Skill；平台前端、后端、
项目数据和运行记录不属于本仓库。

## Skill 目录

| Skill | 用途 |
|---|---|
| `episode-generator` | 分集规划、互动拓扑、完整剧本、逐集复检与组装 |
| `outline-generator` | 互动影游故事大纲与企划基础稿 |
| `nxp-episode-checker` | 分集剧本独立冷读验收 |
| `nxp-plan-storyboard-and-generate-episode-zh` | 剧集优先的故事板与分镜式镜头计划 |
| `故事结构专家` | 互动短剧结构骨架、分支、结局与情绪节拍 |
| `剧本实例化专家` | 把结构骨架实例化为人物、场景、道具和分场剧本 |
| `导演分镜故事版拓展能力` | 把一场戏转成逐镜头分镜和视频提示词 |
| `剧本转分镜图` | 把剧本转成分镜静帧图提示词 |
| `互动影像资产图像提示词生成` | 把正式资产描述转成图像生成提示词 |
| `角色三视图设定表生成能力` | 生成统一版式的角色三视图提示词 |
| `节奏题材校验专家` | 从题材和节奏维度校验互动短剧 |

## 维护边界

- 本仓库是全部正式 Skill 的唯一代码维护仓。
- `interactive-drama-lab` 是独立平台仓，不读取、不 import、不跟随本仓库版本。
- 双方只通过中性 `experiment-report` 交换输入、输出、实验发现和已接受规则。
- 平台结论进入 Skill 前，在本仓库重新判断、实现、测试和发布。
- 各 Skill 的说明、references、scripts 和 agents 元数据只放在对应 Skill 目录内。
- 仓库级历史、维护说明和测试放在根目录，不复制进 Skill 安装包。

项目导航见
[`interactive-content-index`](https://github.com/automaticgrasshopper/interactive-content-index)。

## 版本

多 Skill 仓使用带 Skill 名的 tag，例如：

```text
episode-generator-v0.1.47
outline-generator-v1.0.0
```

历史来源与提取校验见 `PROVENANCE.md`。
