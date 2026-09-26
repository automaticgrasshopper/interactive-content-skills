# Real incremental creation acceptance — 2026-09-26

Scope: local frontend 5194 + own Maxwell preset 8bf0ce65-3d52-4819-97d7-9afbb5751203. No backend/shared CLI/deployment changes. Story 0503c4ee-8942-4a6f-b3aa-348c3d07f227, 《末班船不开灯》.

Natural request: 写一个雨夜末班渡船的悬疑互动故事：一个年轻修船工去找失踪的父亲，在废弃售票亭遇到一个抱着铁盒的陌生女孩，她说父亲就在河对岸，但不肯说铁盒里是什么。先做一个开头，让我决定要不要带她上船。

## Changes
- Skill retains all graph/writer quality references and scripts; new live-creation reference requires distinct meaningful CLI calls for cumulative working text, needed assets, revisions and subsequent nodes. No artificial sleep or finished-story slicing.
- Live frontend applies latest received saved revision immediately; synthetic queue/typewriter is restricted to explicitly requested replay. Locks and original graph/script/asset components retained; new edges retain a short dotted-to-solid visual transition without delaying data.
- Live view releases for AskUser/end so expert handoff is not blocked by a persistent focus view.

## Observed browser event sequence (UTC)
- 04:43:40 opening node received/applied.
- 04:44:00 opening assets applied.
- 04:44:25 opening script 236 chars saved/applied.
- 04:44:42 SAME node script 398 chars saved/applied.
- 04:44:53 next node added.
- 04:45:10 new girl's setting, ticket-booth scene and box were present in the new asset snapshot; focus used the last changed asset.
- 04:45:23 second script 251 chars.
- 04:45:37 SAME script 577 chars.
- 04:45:50 choice/outcome nodes added.
- 04:46:07 new outcome prop applied.
- 04:46:25 companion outcome script 454 chars.
- 04:46:35 solitary outcome script 170 chars.
- 04:46:48 SAME script 443 chars.
- 04:48:35 SAME script revised to 455 chars after a failed dialogue-format check and repair.

These are creation-live applied console events from saved project updates, while the agent was still running. No queued playback was launched. Run ended at expert AskUser after ~8m39s, containing four scripts, one choice, two characters, two scenes and four props. Selected stop; agent ended without further creation. Refreshed page: all five cards and four script buttons persisted; opened second script with complete editable text; asset page independently showed both characters, both scenes and all four props.

## Limits
This validates meaningful saved-paragraph increments, not unpersisted token streaming. Multiple changes may arrive in one backend projection; all data refreshes, focus selects one latest changed item rather than inventing ordered playback. No claim of per-token events or concurrent multi-writer conflict handling. Complex full-auto content passed the previous run, but the new pacing was tested on this bounded expert batch. The experiment still has substantial rule-loading/acceptance overhead; latency optimization and previous identity-binding quality concerns are not declared resolved here.

Validation: TypeScript and scoped ESLint passed; 10 frontend sequence/activity/interrupt tests passed. Existing 17 Skill graph/writer tests passed. No graph or writer validator was weakened.
