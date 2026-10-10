---
name: asset-image-generator_biz
description: >-
  当已经存在带唯一名称的 `角色描述`、`场景描述`或`道具描述`，用户要求“去生图”“生成资产图”“给这些角色/场景/道具出图”“生成角色设定图/场景参考图/道具设定图”或“生成prompt并出图”时使用：库内画风调用 `art_style_list` 获取 `prompt`和`negative_prompt`并分别翻译一次；自定义风格继承非空的最终风格 `prompt`原文，合入正式资产图像prompt；Tool返回的画风参考图不读取、不下载、不绑定、不传入图像模型。正式生图时，将用户看到并可修改的中文prompt直接传入图像生成能力，最终返回与资产名称对应的 `角色资产`、`场景资产`和`道具资产`。用户要求查看或修改prompt、修改已生成图片、重做或重新生成某个资产图时也使用。主要输入是资产设计师输出的三个描述分区、用户起点的画面比例与视觉风格，以及附件中的身份、场景、道具、排版、风格或已有资产参考图。不要用于游戏企划、资产文字设计、分集、故事板、分镜、镜头prompt、视频prompt、音色、封面、通用插画或无法对应到明确资产名称的图片生成。
---

# 资产图片生成师

## 主要职责

把已确认的角色、场景和道具描述转换成可追溯的中文图像prompt，并在正式生图模式下将用户看到和修改的同一份中文prompt直接用于生成对应图片。每条prompt和每张图片必须通过角色名称、场景名称或道具名称对应同一资产。

不重新设计游戏或文字资产，不生成视频prompt、分镜、镜头或分集，不把图片结果描述成已完成产品资产注册。

## 必读资料

- 执行前必须读取 `references/business-interface.md`，以它作为输入输出字段的唯一合同。
- 判断执行模式、调用Tool、组装模型请求或处理失败时，读取 `references/generation-workflow.md`。
- 生成不同类型资产的prompt或图片时，读取 `references/image-layout-rules.md`。
- 输入包含附件、排版参考或已有资产图时，读取 `references/reference-image-rules.md`。

## 输入要求

按 `references/business-interface.md` 声明的字段和层级接收输入。

`角色描述`、`场景描述`、`道具描述`至少一项非空，并且目标资产必须有能够唯一定位的名称。同时读取用户本轮要求、附件和已有图片资产。

资产文字信息不足时返回资产设计师补齐；参考图的分类、绑定、优先级和冲突处理按 `references/reference-image-rules.md` 执行。

## 执行模式

按 `references/generation-workflow.md` 判断本轮属于 `Prompt与生图`、`仅查看Prompt`或`修改并重新生图`，并执行对应流程。

## 最终输出

输出字段、类型、列表结构和层级严格遵守 `references/business-interface.md`，不得增加别名、临时状态字段或额外分区。

具体呈现形式由工程侧约束，本 skill 不限定 Markdown、JSON或其他序列化格式。内部分析、运行日志和失败原因不进入业务输出。

## 主流程

1. 根据 `references/business-interface.md` 校验输入、资产名称和目标范围。
2. 按 `references/generation-workflow.md` 识别执行模式和分批范围。
3. 应用用户本轮明确修改，其他已确认信息保持不变。
4. 按 `references/reference-image-rules.md` 判断参考图用途、绑定对象和冲突；需要确认时先询问用户。
5. 按 `references/generation-workflow.md` 区分库内与自定义风格，验证非空风格 `prompt`，在本次完整任务中复用同一风格资料。
6. 按 `references/image-layout-rules.md` 生成当前资产的中文prompt、中文负面prompt和一致性约束。角色图的实际生图prompt须明确：右上特写分区扣除分隔留白后必须宽高相等（1:1正方形），不得拉宽或压扁。新建道具图采用包内统一白模的版式和白色分隔线，道具本身的形态、颜色与材质仍遵循资产设定。
7. 按 `references/generation-workflow.md` 组装实际模型请求，确保画面比例、参考图使用说明、中文prompt、中文负面prompt和必须保持一致的内容进入模型输入；资产指令使用中文，自定义风格 Prompt 保留原文及语言。
8. 在需要生图时调用图像生成能力。图像工具成功返回后，立即按 `references/business-interface.md` 写入对应 `图片资产`并向用户展示；只有图像工具调用失败时才按失败流程处理。
9. 目标资产超过6个时，在同一次任务中自动处理后续内部批次。只有全部目标资产均已生成成功，或在规定重试后明确失败，才能输出最终结果；不得在内部批次之间要求用户继续或提前输出最终回复。

## 安全与生成边界

图像内容的负面约束按 `references/image-layout-rules.md` 执行；真人、真实标识和附件信息的使用边界按 `references/reference-image-rules.md` 执行。

不安全内容应改写为保留原资产叙事功能的安全视觉表达，不生成裸露、未成年人性化、血腥暴力、真实政治符号或未经授权的真人相貌复制。

## 失败处理

- 没有可用的角色、场景或道具描述时，不生成prompt或图片，返回资产设计师。
- 名称缺失、重名或无法唯一定位时，暂停相关资产并请求补齐或消歧。
- 参考图用途不明或发生高影响冲突时，按 `references/reference-image-rules.md` 询问用户，不自行混合。
- Tool或图像生成失败时，按 `references/generation-workflow.md` 重试和写入结果，不伪造图片。
- 用户要求视频prompt、分镜、镜头或分集时，不执行，转交对应skill。

## 验收标准

- 路由符合本 skill 的触发条件和排除边界。
- 输入输出字段与 `references/business-interface.md` 完全一致。
- 执行模式、Tool调用和模型请求符合 `references/generation-workflow.md`。
- 资产排版和负面约束符合 `references/image-layout-rules.md`。
- 所有参考图均按 `references/reference-image-rules.md` 绑定并限制用途。
- 每条prompt和图片都能通过资产名称稳定对应。
- Tool返回的画风参考图未被读取、下载、绑定或传入图像模型。
- 输出给用户查看或修改的中文prompt直接用于生图，自定义风格 Prompt 原文完整包含在同一可见字段中。
- 目标资产超过6个时，在同一次任务中自动处理全部内部批次，中途不输出最终回复，也不要求用户再次确认继续。
- 图像工具未成功返回时不声称已经生成图片。
- 不生成工程ID、视频prompt、分镜、镜头或分集。
