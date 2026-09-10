# 图形提交与检查

机器只检查图形、用户数量及合同/投影完整性，不判断剧情、情绪或虚构状态。只需Python标准库。

## 提交

freeze之后先写支线完整故事，再切片、组织正式图。第一次提交前保留简短 exploration.md 探索草图；它只是废弃草图，不要求通过正式检查。

SUBMISSION.json：

```json
{
  "expected_hash":null,
  "reason":"首次正式图",
  "affected_nodes":[],
  "branches":{"stories":[{"complete_story":"一条完整支线到回汇或结局的连续原文","episodes":[{"id":"b1","title":"支线剧集","text":"原文切片","conflict":"实际冲突","stop_boundary":"本集停止点"}]}]},
  "plan":{
    "mainline_path":["n1","c1","n2"],
    "nodes":[
      {"id":"n1","kind":"scene","source":"m1","next":["c1"],"ending_type":null},
      {"id":"c1","kind":"choice","question":"当前如何行动？","options":[{"text":"主线动作","target":"n2"},{"text":"支线动作","target":"n3"}]},
      {"id":"n2","kind":"ending","source":"m2","next":[],"ending_type":"main"},
      {"id":"n3","kind":"ending","source":"b1","next":[],"ending_type":"small"}
    ]
  }
}
```

示例只说明字段，不是完整合格图形；真实mainline.json须有m1/m2且默认还需四类结局等门禁。非选择节点不重复正文，只引用故事切片source；每份切片恰好用于一个节点。kind只能scene/choice/ending。所有连线从next或options唯一派生，不另写第二套edges。默认每个选择2—4个互斥动作。

mainline_path必须从入口连续走到结局，穿过的非选择节点按序对应mainline全部切片。第一次submit固定该路径及其节点（包括路径上的选择），支线返工不能改变它们。请在冻结前为主线完整设置真实抉择；缺深度在支线补，不在主线插剧情。

```bash
python3 scripts/route_plan.py freeze CACHE_ROOT
python3 scripts/route_plan.py submit CACHE_ROOT SUBMISSION.json
python3 scripts/route_plan.py check CACHE_ROOT
```

submit可接受基础结构合法但复杂度不够的正式候选，保存各项结果，供局部修复；不能正式交付。check派生graph-report.json与route-candidate.json。候选不可手改；梗概由完整故事原文切片原样生成。

## 图形硬门禁

- 基础：一个非选择入口，无环、无不可达节点、无断头；scene恰有一个后继，choice至少两个不同目标，ending无后继。选项目标必须先落到独立剧集，不能用连续选择卡代替剧情后果。
- 数量：四项用户硬数量分别核对；一集不含选择，所有结局合计兑现用户数量。
- 结局：未指定数量或类型时，小结局small、期望expected、坏结局failure、真结局main各至少一个；包括短故事。用户覆盖只在冻结输入时声明。
- 非短故事（>=15分钟）：必须有小结局；必须有有效交叉回汇；必须至少两层分岔。用户类型覆盖或明确结构要求优先。短故事不强制交叉与深度，默认四结局仍在。
- 交叉：同一选择的两条路线，从各自不同的非结局剧集出发，以内部节点互不重合的路径进入同一后续非结局剧集。程序用两单位顶点容量流找实际路径；画面线条交叉不算。
- 深度：第二个选择位于前一个选择的部分支路上，其他支路不会同样必经它，才增加嵌套层级；普通串节点或串联公共小菱形不算第二层。
- 三个及以上主要结局时，计算各结局首次变成唯一可达的锁定选择，至少分布在两个不同选择；不允许最后一题统一分配全部主要结局。小结局不参与主要结局锁定统计。

报告另外给出全部路径数、选项数、交叉路径与递进结局形状。递进结构为偏好，不额外设硬配额；程序只能识别形状，作者负责期待已兑现及真结局的实际含义。完整路线可用 `route_plan.py paths CACHE_ROOT` 流式导出，计数使用DAG动态规划，不截断或用路径数冒充复杂度。
