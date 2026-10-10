#!/usr/bin/env python3
"""Read-only shape evidence from persisted nextplay.route.v1 nodes and edges.

This checks topology, not genre, narrative merit, or whether a merge is justified.
Only call for an expert opening; it imposes no rule on later batches.
"""
import argparse
import json
from collections import deque
from itertools import combinations
from pathlib import Path


def inspect(route):
    if route.get('schema_version') != 'nextplay.route.v1':
        raise ValueError('Expected a persisted nextplay.route.v1 readback')
    data = route['data']
    nodes = data['nodes']
    by = {n['node_ref']: n for n in nodes}
    if not nodes or len(nodes) != len(by):
        raise ValueError('Empty route or duplicate node refs')
    succ = {n: [] for n in by}
    degree = dict.fromkeys(by, 0)
    for edge in data['edges']:
        a, b = edge['source_node_ref'], edge['target_node_ref']
        if a not in by or b not in by:
            raise ValueError('Dangling edge')
        if b not in succ[a]:
            succ[a].append(b)
            degree[b] += 1
    entry = data['entry_node_ref']
    if entry not in by:
        raise ValueError('Invalid entry')
    queue = deque(n for n, d in degree.items() if d == 0)
    order = []
    while queue:
        n = queue.popleft()
        order.append(n)
        for target in succ[n]:
            degree[target] -= 1
            if degree[target] == 0:
                queue.append(target)
    if len(order) != len(by):
        raise ValueError('Opening shape audit requires an acyclic route')
    reach = {}
    for n in reversed(order):
        reach[n] = {n}.union(*(reach[t] for t in succ[n]))
    if reach[entry] != set(by):
        raise ValueError('Unreachable nodes')
    first = entry
    while by[first]['node_type'] != 'choice':
        if len(succ[first]) != 1:
            raise ValueError('No unique first choice after the opening')
        first = succ[first][0]
    targets = succ[first]
    if len(targets) < 2 or any(by[t]['node_type'] != 'video' for t in targets):
        raise ValueError('First choice needs distinct narrative consequences')
    video = lambda n: by[n]['node_type'] == 'video'
    ending = lambda n: bool(by[n].get('metadata', {}).get('is_ending'))
    pairs = []
    shapes = set()
    for a, b in combinations(targets, 2):
        shared = {n for n in reach[a] & reach[b] if video(n) and not ending(n)}
        # Earliest common scenes form an antichain, not just the first in file order.
        first_merges = {n for n in shared if not any(n != x and n in reach[x] for x in shared)}
        private = [reach[a] - reach[b], reach[b] - reach[a]]
        decisions = [{n for n in arm if by[n]['node_type'] == 'choice'
                      and (not first_merges or any(m in reach[n] for m in first_merges))}
                     for arm in private]
        terminals = [{n for n in reach[t] if not succ[n]} for t in (a, b)]
        closed = [bool(ts) and all(ending(n) for n in ts) for ts in terminals]
        if closed[0] != closed[1]:
            shapes.add(3)
        if all(decisions):
            woven = len(first_merges) >= 2 and all(
                any(first_merges <= reach[q] for q in qs) for qs in decisions)
            shape = 6 if woven else 5
        elif any(decisions):
            shape = 4
        elif first_merges:
            shape = 2
        elif closed[0] != closed[1]:
            shape = 3
        else:
            shape = 1
        shapes.add(shape)
        pairs.append({'targets': [a, b], 'shape': shape,
                      'first_shared_scenes': sorted(first_merges),
                      'private_choices_before_merge': [sorted(q) for q in decisions],
                      'terminal_refs': [sorted(ts) for ts in terminals]})
    return {'status': 'TOPOLOGY_EVIDENCE', 'revision': route['revision'],
            'entry': entry, 'first_choice': first, 'shape_ids': sorted(shapes),
            'choice_outdegree': len(targets), 'pairs': pairs,
            'narrative_merge_review': 'REQUIRED',
            'note': 'IDs and edges prove shape only; titles, layout and claimed costs do not.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('readback', type=Path)
    parser.add_argument('--expect', type=int, choices=range(1, 7), nargs='+')
    args = parser.parse_args()
    try:
        report = inspect(json.loads(args.readback.read_text()))
        if args.expect and not set(args.expect) <= set(report['shape_ids']):
            report['status'] = 'SHAPE_MISMATCH'
            report['expected'] = args.expect
            code = 1
        else:
            code = 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        report = {'status': 'INVALID_READBACK', 'error': str(error)}
        code = 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
