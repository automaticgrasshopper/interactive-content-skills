# 完整故事与分集拆解

本文件只定义私有创作材料和阶段二门禁，不增加正式业务字段。

## 一、四层材料不得混用

1. `story-treatment.json`回答全篇实际发生什么、为什么发生，以及不同选择如何改变后续。
2. `topology.md`只把已经成立的故事投影成节点和连接，不新增剧情。
3. `episode-synopses/*.json`把完整故事切成各集承担的连续因果变化，不重新构思故事。
4. `episodes/*.md`把冻结梗概演成可执行剧本，不改写故事、拓扑或梗概。

完整故事不是线性主线。存在互动时，必须在写作时同时写清选择原因、各选项后果、持续差异和汇合或结局；禁止先写一条线性故事，再把选择焊上去。

## 二、完整故事合同

使用`nextplay.episode-story-treatment.v1`：

```json
{
  "contract_version": "nextplay.episode-story-treatment.v1",
  "title": "故事标题",
  "complete_story": "从开场到全部结局均可独立读懂的连续自然语言故事。共同主线与各分支均写入正文。",
  "choices": [
    {
      "choice_id": "choice-001",
      "dramatic_cause": "前文哪组行动、阻力和价值冲突逼出这个选择",
      "question": "玩家此刻真正需要决定的问题",
      "options": [
        {
          "option_id": "A",
          "option_text": "玩家可执行动作",
          "immediate_consequence": "选择后先发生的不同事件",
          "lasting_difference": "此后仍被承接的关系、信息、风险、资源或承诺差异"
        }
      ],
      "merge_or_ending": "取得什么共同事实后汇合，或分别进入哪个结局"
    }
  ],
  "endings": [
    {
      "title": "结局标题",
      "kind": "formal",
      "causal_payoff": "该结局回收了哪些前置行动与选择，人物得到和失去什么"
    }
  ]
}
```

规则：

- 根对象只能有以上五个字段；`kind`只能为`formal`或`failure`。
- `complete_story`必须是连续可读故事，写出感知、判断、欲望、行动、阻力、调整和可见后果，不能用设定、主题、节点标题或事件清单代替。
- `choices`数量以真实戏剧裂缝为准。每个选项必须有不同的即时后果和持续差异；无法说明差异时删除该选择。
- `endings`必须覆盖阶段一冻结的全部结局方向。结局回收写清因果，不用价值口号代替发生的事件。
- 人物、资产、世界规则和知情边界只能来自已冻结上游。完整故事不得创造未登记的重要角色、场景或道具。

## 三、完整故事冷读

`story_treatment_gate.py packet`只提供冻结基础、用户意图和完整故事，不提供预期答案。独立冷读结果使用：

```json
{
  "treatment_sha256": "packet中的值",
  "run_basis_sha256": "packet中的值",
  "asset_catalog_sha256": "packet中的值",
  "user_intent_source_sha256": "packet中的值",
  "user_intent_contract_sha256": "packet中的值",
  "comprehension": {
    "protagonist_goal": {"answer": "主角为什么必须行动", "proof": "完整故事逐字证据"},
    "causal_progression": {"answer": "行动如何因阻力而调整并产生后果", "proof": "完整故事逐字证据"},
    "branch_logic": {"answer": "选择为何出现且各路线如何真正不同", "proof": "完整故事或选择记录逐字证据"},
    "ending_payoffs": {"answer": "各结局如何由前文累积产生", "proof": "完整故事或结局记录逐字证据"}
  },
  "covered_checks": [
    "用户要求与上游事实",
    "人物动机与知情边界",
    "全篇因果连续",
    "分支即时差异与持续承接",
    "汇合共同事实",
    "结局因果回收",
    "信息吞吐与后段完整度"
  ],
  "evidence": [
    {"check": "检查名称", "proof": "完整故事逐字证据", "explanation": "证据如何支持判断"}
  ],
  "issues": []
}
```

四项理解证据必须互不相同，不能用同一句套答。七项检查必须全部覆盖并分别举证。任一问题存在时如实写入`issues`并返修；不得先清空问题再封存。

## 四、从完整故事投影拓扑

- 情绪脊先给出全篇状态变化和真实拐点；完整故事把这些变化写成事件。
- 拓扑节点只切分完整故事中已经存在的戏剧单位。
- 拓扑中的每个选择问题、选项文字和结局标题必须与`story-treatment.json`逐项一致。
- 拓扑可以为一个选项安排多个后续节点，但第一个目标必须演出该选项的即时后果。
- 选择后的路线只有取得`merge_or_ending`声明的共同事实后才能汇合。
- 完整故事没有的事件、选择或结局不得由拓扑新增；无法投影时退回完整故事阶段。

## 五、全体梗概合同与拆解

每集仍使用`nextplay.episode-synopsis.v1`。必须一次生成与冻结拓扑完全对应的全部梗概，再整体复检；任何完整剧本都不得先于梗概集合回执出现。

每集梗概必须是一个完整的因果变化，而不是事实列表：

```text
既定处境与关系
→ 当前目标或问题
→ 初始行动
→ 有效阻力
→ 调整
→ 可见结果
→ 下一压力、行动或真实选择
```

允许省略不影响理解的连接动作，但不得省略造成转折的行动、阻力、调整或结果。梗概只写本集将实际演出的事件；前史必须在本集被回忆、讲述、发现或影响当前行动时才可写入。

## 六、梗概集合冷读

`synopsis_set_gate.py packet`提供完整故事、拓扑和全部梗概。复检结果使用：

```json
{
  "synopsis_set_sha256": "packet中的值",
  "treatment_sha256": "packet中的值",
  "topology_sha256": "packet中的值",
  "user_intent_source_sha256": "packet中的值",
  "user_intent_contract_sha256": "packet中的值",
  "covered_checks": [
    "完整覆盖且无重复",
    "事件顺序与因果连续",
    "分支隔离与汇合条件",
    "结局路线承接",
    "逐集戏剧单位完整",
    "各集推进量与后段完整度"
  ],
  "episode_checks": [
    {
      "episode_id": "episode-001",
      "situation_goal_proof": "本集梗概逐字证据",
      "action_resistance_adjustment_proof": "本集梗概逐字证据",
      "result_next_entry_proof": "本集梗概逐字证据",
      "treatment_source_proof": "完整故事逐字证据"
    }
  ],
  "evidence": [
    {"check": "检查名称", "proof": "梗概或完整故事逐字证据", "explanation": "证据如何支持集合判断"}
  ],
  "issues": []
}
```

每个冻结节点必须且只能出现一条`episode_checks`。三段梗概证据分别证明处境目标、行动阻力调整、结果下一入口；不得重复使用同一段代替三项。`treatment_source_proof`证明本集事件确实来自完整故事。

集合门禁通过后，任一梗概、完整故事或拓扑变化都会使回执失效。发现单集梗概有问题时，修复受影响梗概后必须重新运行整个集合门禁；这不是重新创作故事，而是重新确认拆解仍完整。
