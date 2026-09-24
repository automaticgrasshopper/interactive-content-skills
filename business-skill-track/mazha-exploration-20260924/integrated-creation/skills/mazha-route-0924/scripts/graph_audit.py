#!/usr/bin/env python3
"""Read-only audit: original DAG checks plus explicit batch/loop boundaries.

Loop structure never masquerades as a successful advanced DAG audit.
"""
import argparse
import json
from collections import deque
from pathlib import Path
from graph_check import inspect, ENDINGS


def reachable(start, succ):
    seen, pending = set(), [start]
    while pending:
        item = pending.pop()
        if item not in seen:
            seen.add(item)
            pending.extend(succ[item])
    return seen


def acyclic(succ):
    degree = dict.fromkeys(succ, 0)
    for targets in succ.values():
        for target in targets:
            degree[target] += 1
    queue = deque(n for n, d in degree.items() if not d)
    visited = 0
    while queue:
        n = queue.popleft()
        visited += 1
        for target in succ[n]:
            degree[target] -= 1
            if not degree[target]:
                queue.append(target)
    return visited == len(succ)


def audit(plan, policy):
    nodes = plan['nodes']
    by = {n['id']: n for n in nodes}
    if not nodes or len(by) != len(nodes):
        raise ValueError('Empty graph or duplicate IDs')
    scope = policy.get('scope', 'full')
    if scope not in ('full', 'batch'):
        raise ValueError('scope must be full or batch')
    frontiers = set(policy.get('frontiers', []))
    if not frontiers <= by.keys() or (scope == 'full' and frontiers):
        raise ValueError('Invalid frontiers: full work cannot have unfinished nodes')
    succ, prev = {n: [] for n in by}, {n: [] for n in by}
    for n in nodes:
        kind = n['kind']
        if kind == 'choice':
            if set(n) != {'id','kind','question','options'} or not n['question'].strip():
                raise ValueError('Invalid choice fields')
            options = n['options']
            targets = [o['target'] for o in options]
            if len(targets) < 2 or len(set(targets)) != len(targets):
                raise ValueError('Choice must have at least two distinct targets')
            if any(set(o) != {'text','target'} or not o['text'].strip() for o in options):
                raise ValueError('Invalid choice option')
        elif kind in ('scene', 'ending'):
            if set(n) != {'id','kind','source','next','ending_type'} or not n['source']:
                raise ValueError('Invalid narrative fields')
            targets = n['next']
            if kind == 'ending':
                if targets or n['ending_type'] not in ENDINGS:
                    raise ValueError('Ending must be terminal with valid type')
            elif n['ending_type'] is not None or len(targets) != (0 if n['id'] in frontiers else 1):
                raise ValueError('Only explicitly declared batch frontier scenes may be unfinished')
        else:
            raise ValueError('Invalid kind')
        if n['id'] in frontiers and kind != 'scene':
            raise ValueError('A frontier must be an unfinished scene, not choice or ending')
        for t in targets:
            if t not in by or t == n['id']:
                raise ValueError('Dangling or self edge')
            if kind == 'choice' and by[t]['kind'] == 'choice':
                raise ValueError('Each choice must first have a narrative consequence')
            succ[n['id']].append(t)
            prev[t].append(n['id'])
    entries = [n for n in by if not prev[n]]
    if len(entries) != 1 or by[entries[0]]['kind'] != 'scene':
        raise ValueError('Exactly one narrative entry is required; put one-time intro outside the loop')
    if reachable(entries[0], succ) != by.keys():
        raise ValueError('Unreachable nodes')
    terminals = {n for n in by if by[n]['kind'] == 'ending'} | frontiers
    if any(not reachable(n, succ) & terminals for n in by):
        raise ValueError('A node cannot reach an ending or declared batch frontier')
    loops = plan.get('loops', [])
    cyclic = not acyclic(succ)
    if cyclic and policy.get('loop_authorization') not in ('explicit_user_request', 'existing_canvas'):
        raise ValueError('Free topology is acyclic; loops require explicit request or existing canvas')
    if cyclic and not loops:
        raise ValueError('Undeclared cycle')
    if loops and not cyclic:
        raise ValueError('Loop declaration has no actual cycle')
    returns = set()
    evidence = []
    for loop in loops:
        hub, choice = loop['hub'], loop['choice']
        if hub not in by or choice not in by or by[hub]['kind'] != 'scene' or by[choice]['kind'] != 'choice' or succ[hub] != [choice]:
            raise ValueError('Loop hub must be narrative directly before its choice')
        forward = reachable(hub, succ)
        component = {n for n in forward if hub in reachable(n, succ)}
        if len(component) < 3 or choice not in component:
            raise ValueError('Loop must include choice and narrative consequence')
        if not str(loop.get('repeat_contract', '')).strip():
            raise ValueError('Missing repeat-entry story contract')
        if loop.get('state_mode') not in ('repeat_safe', 'conditional'):
            raise ValueError('Unknown loop state mode')
        if not loop.get('returns') or not loop.get('exits'):
            raise ValueError('Loop requires return edges and a real exit')
        for edge in loop['returns']:
            s, t = edge['source'], edge['target']
            if s not in component or t != hub or t not in succ[s] or by[s]['kind'] != 'scene' or s == hub:
                raise ValueError('Return must run from narrative consequence to declared hub')
            if (s,t) in returns:
                raise ValueError('Duplicate return declaration')
            returns.add((s,t))
        for edge in loop['exits']:
            s,t = edge['source'], edge['target']
            if s not in component or t not in by or t not in succ[s] or t in component:
                raise ValueError('Exit must actually leave the loop component')
            if not reachable(t, succ) & terminals:
                raise ValueError('Loop exit cannot reach completion/frontier')
        evidence.append({'hub': hub, 'choice': choice, 'component': sorted(component), 'exits': loop['exits'], 'state_mode': loop['state_mode']})
    if cyclic:
        # This graph is ONLY used to detect undeclared residual cycles. It is
        # never passed to inspect or presented as a valid whole-work projection.
        forward_only = {s: [t for t in ts if (s,t) not in returns] for s,ts in succ.items()}
        if not acyclic(forward_only):
            raise ValueError('Cycle not covered by declared return edges')
    counts = {'episode_count': sum(n['kind'] != 'choice' for n in nodes),
              'choice_node_count': sum(n['kind'] == 'choice' for n in nodes),
              'ending_count': sum(n['kind'] == 'ending' for n in nodes), 'total_node_count': len(nodes)}
    failures = []
    for key, value in policy.get('hard_counts', {}).items():
        if value is not None and counts.get(key) != value:
            failures.append('USER_COUNT:' + key)
    if scope == 'full' and not cyclic:
        report = inspect(plan, policy)
        report.update({'scope':'full', 'loop_structure':[], 'narrative_review':'REQUIRED'})
        return report
    if scope == 'full':
        kinds = {n['ending_type'] for n in nodes if n['kind'] == 'ending'}
        if not set(policy['required_endings']) <= kinds:
            failures.append('ending_types')
        if set(policy['forbidden_endings']) & kinds:
            failures.append('USER_ENDING_FORBIDDEN')
    return {'status': 'NEEDS_REPAIR' if failures else ('REVIEW_REQUIRED' if cyclic else 'BATCH_STRUCTURE_PASS'),
            'scope': scope, 'failures': failures, 'counts': counts, 'frontiers': sorted(frontiers),
            'loop_structure': evidence, 'path_count': None,
            'advanced_topology': 'AUTHOR_EVIDENCE_REQUIRED' if scope == 'full' else 'NOT_A_FULL_WORK_AUDIT',
            'runtime_loop_support': 'UNVERIFIED' if cyclic else 'NOT_APPLICABLE',
            'narrative_review': 'REQUIRED'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('plan', type=Path)
    parser.add_argument('policy', type=Path)
    args = parser.parse_args()
    try:
        report = audit(json.loads(args.plan.read_text()), json.loads(args.policy.read_text()))
    except (ValueError, KeyError, TypeError, OSError) as error:
        report = {'status':'INVALID_INPUT_OR_STRUCTURE', 'error':str(error)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
