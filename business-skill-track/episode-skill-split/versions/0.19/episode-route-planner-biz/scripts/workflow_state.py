#!/usr/bin/env python3
"""Resume the single-candidate, one-frontier-at-a-time route workflow."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any

UPSTREAM_STEPS = (
    ('user-request.md', 'CAPTURE_USER_REQUEST'),
    ('user-intent-lock.json', 'BUILD_USER_INTENT_LOCK'),
    ('creative-brief.json', 'BUILD_CREATIVE_BRIEF'),
    ('complete-story.json', 'WRITE_COMPLETE_STORY'),
    ('mainline-decomposition.json', 'BUILD_MAINLINE_DECOMPOSITION'),
    ('mainline-emotional-movement.json', 'BUILD_MAINLINE_EMOTIONAL_MOVEMENT'),
    ('decision-fissure-audit.json', 'BUILD_MAINLINE_FISSURES'),
)
DOWNSTREAM_FILES = ('growth-state.json', 'route-candidate.json', 'topology-review.json', 'emotional-spine.json', 'planning-acceptance.json')
RETIRED_FILES = ('story-treatment.json', 'topology-draft-1.json', 'topology-draft-2.json', 'topology-comparison-packet.json', 'topology-comparison-verdict.json', 'topology-selection.json', 'route-evidence-bindings.json')

def action(name: str, **details: Any) -> dict[str, Any]:
    return {'status': 'IN_PROGRESS', 'next_actions': [{'action': name, 'execution_mode': 'current_task', **details}]}

def status(cache_root: Path) -> dict[str, Any]:
    root = cache_root.resolve()
    if not (root / 'growth-state.json').exists():
        return planned_status(root)
    retired = [name for name in RETIRED_FILES if (root / name).exists()]
    if retired:
        raise ValueError('本轮不接受预写支线或旧双版拓扑文件：' + '、'.join(retired))
    names = [name for name, _ in UPSTREAM_STEPS]
    latest = -1
    for index, (name, next_action) in enumerate(UPSTREAM_STEPS):
        path = root / name
        if not path.is_file():
            future = [n for n in names[index + 1:] + list(DOWNSTREAM_FILES) if (root / n).exists()]
            if future:
                raise ValueError('发现越过当前阶段的产物：' + '、'.join(future))
            return action(next_action)
        current = path.stat().st_mtime_ns
        # File timestamps can change after JSON-format fixes or copying.
        # Presence gates enforce stages; growth replay verifies frozen content hashes.
        latest = current
    if not (root / 'growth-state.json').is_file():
        if any((root / n).exists() for n in DOWNSTREAM_FILES[1:]):
            raise ValueError('缺少逐步生长记录，禁止直接提交完整路线')
        return action('INIT_GROWTH', command='python3 scripts/route_growth.py init CACHE_ROOT')
    from route_growth import status as growth_status, verify_root as verify_growth
    growth = growth_status(root)
    if growth['status'] != 'COMPLETE':
        if any((root / n).exists() for n in DOWNSTREAM_FILES[1:]):
            raise ValueError('路径尚未全部关闭，禁止提前生成正式候选或验收')
        return action('ADVANCE_ONE_FRONTIER', state_hash=growth['state_hash'], frontier=growth['next_frontier'], command='python3 scripts/route_growth.py append CACHE_ROOT STEP.json')
    if not (root / 'route-candidate.json').is_file():
        if any((root / n).exists() for n in DOWNSTREAM_FILES[2:]):
            raise ValueError('尚未投影正式候选，禁止提前验收')
        return action('MATERIALIZE_GROWTH', command='python3 scripts/route_growth.py materialize CACHE_ROOT')
    issues = verify_growth(root)
    if issues:
        raise ValueError('生长记录或正式候选不一致：' + '；'.join(issues))
    intent = json.loads((root / 'user-intent-lock.json').read_text())
    if intent.get('shape_mode') == 'exact':
        steps = [('planning-acceptance.json', 'ACCEPT_PLANNING')]
    else:
        steps = [('topology-review.json', 'REVIEW_ROUTE_ONCE'), ('emotional-spine.json', 'PROJECT_EMOTIONAL_SPINE'), ('planning-acceptance.json', 'ACCEPT_PLANNING')]
    latest = (root / 'route-candidate.json').stat().st_mtime_ns
    for index, (name, next_action) in enumerate(steps):
        path = root / name
        if not path.is_file():
            if any((root / n).exists() for n, _ in steps[index+1:]):
                raise ValueError('发现越过当前验收步骤的产物')
            return action(next_action)
        if path.stat().st_mtime_ns < latest:
            raise ValueError('下游验收早于当前依赖，已过期')
        latest = path.stat().st_mtime_ns
    from planning_gate import verify_root
    issues = verify_root(root)
    if issues:
        raise ValueError('规划回执失效：' + '；'.join(issues))
    return {'status': 'COMPLETE', 'next_actions': []}

def planned_status(root):
    for name, next_action in UPSTREAM_STEPS:
        if not (root/name).exists(): return action(next_action)
    if not (root/'story-treatment.json').exists(): return action('PLAN_BRANCH_CONSEQUENCES')
    if not (root/'topology-state.json').exists():
        return action('FREEZE_TOPOLOGY', command='python3 scripts/topology_plan.py freeze CACHE_ROOT PLAN.json')
    import topology_plan as topology
    import planned_gate
    topology.load(root)
    if not (root/'route-ledger.json').exists():
        return action('DERIVE_ROUTE_LEDGER',command='python3 scripts/topology_plan.py ledger CACHE_ROOT')
    planned_gate.packet(root)
    for which in ('A','B'):
        if not (root/f'topology-review-{which}.json').exists(): return action(f'REVIEW_TOPOLOGY_{which}')
        planned_gate.review(root,which)
    if not (root/'episode-synopses.json').exists(): return action('PROJECT_SYNOPSES')
    if not (root/'route-candidate.json').exists():
        return action('MATERIALIZE_SYNOPSES',command='python3 scripts/topology_plan.py materialize CACHE_ROOT')
    if not (root/'synopsis-review.json').exists(): return action('REVIEW_SYNOPSES')
    planned_gate.synopsis_review(root,topology.materialize(root))
    if not (root/'emotional-spine.json').exists(): return action('PROJECT_EMOTIONAL_SPINE')
    if not (root/'planning-acceptance.json').exists(): return action('ACCEPT_PLANNING')
    from planning_gate import verify_root
    errors=verify_root(root)
    if errors: raise ValueError('规划回执失效：'+'；'.join(errors))
    return {'status':'COMPLETE','next_actions':[]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('cache_root', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(status(args.cache_root), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'FAIL: {error}')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
