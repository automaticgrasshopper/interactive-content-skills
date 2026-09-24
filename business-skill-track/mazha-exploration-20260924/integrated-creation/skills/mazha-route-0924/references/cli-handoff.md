# CLI 做项目工程，Skill 做创作

先加载当前绑定的 nextplay-cli 入口，按真实文档初始化一次；只在工具能力不明时读相关 help／schema。不能凭此文档猜完整命令参数或自行补 runtime.env、密钥、项目身份。

读取当前 manifest、inspect 与必要节点／资产，确认当前用户作品和实际版本。outline 保存提案，asset add/update 保存文字，route create/edit 保存节点连线，script set/edit 保存正文；使用 CLI 真实支持的路径和参数，遵守 dry-run、并发检查、校验、保存与读回。工具本身已保存读回就不再调用旧网关重复保存。

- route create 仅用于空图，返回的 reference_map 是新 client_key 到稳定引用的依据；已有图用 edit 保留稳定 ID 与媒体。
- 内部 graph_check 的 scene/choice/ending 是创作投影；平台以 CLI 实际 schema 为准。不要直接把整个内部 JSON 写进 route。
- 专家待续末端是未完成的普通剧情，不伪造 is_ending；CLI 如允许保存未连接末端，记录 warning 与续写计划，不能把本批状态说成作品可发布。若拒绝，报告具体限制，不能绕过写文件。
- script 只写剧情节点。正文中实际出现的人物、场景、道具用真实资产 ref 的 mentions；名称到 ref 映射以读回为准。编辑正文保留无关 mentions 与媒体，实际不再出现的引用同步调整。
- 全自动可一批提交完整选择与后果，避免展示半个失效选择卡；保存后继续写，前端消费实际变化并渐显，不等待动画完成再工作。
- partial_saved／冲突先读实际结果，仅补未成功部分，不把整批重放成重复节点。工具不支持的条件、变量、动态选项不得写入自造字段。

CLI 的 PASS 证明工程合同与保存结果，不证明 woven、情绪脊、情节连贯或写作合格。反之内部创作检查不是平台权限；平台拒绝保存不能用人工验收绕过。初始化、读取和写入错误只作简短准确说明，内部命令、hash 与制作话语不进玩家剧本。
