"""Graph-only checks. No evaluation of plot, emotion, prose or fictional state."""
from collections import deque
from itertools import combinations

KINDS = {'scene', 'choice', 'ending'}
ENDINGS = {'small', 'expected', 'failure', 'main'}


def structure(plan):
    nodes = plan['nodes']
    by = {n['id']: n for n in nodes}
    if not nodes or len(by) != len(nodes):
        raise ValueError('STRUCTURE: empty graph or duplicate IDs')
    succ = {i: [] for i in by}
    prev = {i: [] for i in by}
    for n in nodes:
        if n['kind'] not in KINDS:
            raise ValueError('STRUCTURE: invalid node kind')
        if n['kind'] == 'choice':
            if set(n) != {'id', 'kind', 'question', 'options'} or not n['question'].strip():
                raise ValueError('STRUCTURE: choice contains story or misses question')
            targets = [o['target'] for o in n['options']]
            if len(targets) < 2 or len(set(targets)) != len(targets):
                raise ValueError('STRUCTURE: choice needs distinct targets')
            if any(set(o) != {'text', 'target'} or not o['text'].strip() for o in n['options']):
                raise ValueError('STRUCTURE: invalid option')
        else:
            if set(n) != {'id', 'kind', 'source', 'next', 'ending_type'}:
                raise ValueError('STRUCTURE: episode fields must match contract')
            targets = n['next']
            if n['kind'] == 'ending':
                if targets or n['ending_type'] not in ENDINGS:
                    raise ValueError('STRUCTURE: ending must be terminal with valid type')
            elif len(targets) != 1 or n['ending_type'] is not None:
                raise ValueError('STRUCTURE: scene needs one successor')
        for t in targets:
            if t not in by or t == n['id']:
                raise ValueError(f'STRUCTURE: invalid edge {n["id"]}->{t}')
            succ[n['id']].append(t)
            prev[t].append(n['id'])
    entries = [i for i in by if not prev[i]]
    if len(entries) != 1 or by[entries[0]]['kind'] == 'choice':
        raise ValueError('STRUCTURE: exactly one narrative entry required')
    degrees = {i: len(prev[i]) for i in by}
    queue = deque(entries)
    order = []
    while queue:
        i = queue.popleft()
        order.append(i)
        for j in succ[i]:
            degrees[j] -= 1
            if degrees[j] == 0:
                queue.append(j)
    if len(order) != len(by):
        raise ValueError('STRUCTURE: cyclic or unreachable nodes')
    reach, ends, path_counts = {}, {}, {}
    for i in reversed(order):
        reach[i] = {i}.union(*(reach[j] for j in succ[i]))
        ends[i] = {i} if not succ[i] else set().union(*(ends[j] for j in succ[i]))
        path_counts[i] = sum(path_counts[j] for j in succ[i]) if succ[i] else 1
    return by, succ, prev, order, reach, ends, path_counts[entries[0]]


def disjoint_paths(a, b, target, succ):
    """Two vertex-disjoint branch paths to a common merge, by unit max-flow."""
    source = ('source', '')
    sink = (target, 'in')
    cap, original = {}, {}
    def edge(u, v):
        cap[u, v] = original[u, v] = 1
        cap.setdefault((v, u), 0)
    for i in succ:
        if i == target:
            continue
        edge((i, 'in'), (i, 'out'))
        for j in succ[i]:
            edge((i, 'out'), (j, 'in'))
    edge(source, (a, 'in'))
    edge(source, (b, 'in'))
    adj = {}
    for u, v in cap:
        adj.setdefault(u, []).append(v)
    for _ in range(2):
        parent = {source: None}
        queue = deque([source])
        while queue and sink not in parent:
            u = queue.popleft()
            for v in adj.get(u, []):
                if cap[u, v] and v not in parent:
                    parent[v] = u
                    queue.append(v)
        if sink not in parent:
            return None
        v = sink
        while parent[v] is not None:
            u = parent[v]
            cap[u, v] -= 1
            cap[v, u] += 1
            v = u
    paths = []
    for start in (a, b):
        p, u = [start], (start, 'in')
        while u != sink:
            outgoing = [v for v in adj[u] if original.get((u, v)) == 1 and cap[u, v] == 0]
            if not outgoing:
                return None
            v = outgoing[0]
            if v[1] == 'in':
                p.append(v[0])
            u = v
        paths.append(p)
    return paths


def inspect(plan, policy):
    by, succ, prev, order, reach, ends, count = structure(plan)
    choices = [i for i in order if by[i]['kind'] == 'choice']
    terminals = [i for i in order if by[i]['kind'] == 'ending']
    counts = {'episode_count': len(by)-len(choices), 'choice_node_count': len(choices),
              'ending_count': len(terminals), 'total_node_count': len(by)}
    failures, checks = [], {}
    def check(key, passed, evidence, required=True):
        exempt = policy['exemptions'].get(key)
        checks[key] = {'status': 'EXEMPT' if exempt else ('PASS' if passed else ('FAIL' if required else 'ADVISORY')),
                       'evidence': evidence, 'exemption': exempt}
        if required and not passed and not exempt:
            failures.append(key)
    for k, expected in policy['hard_counts'].items():
        if expected is not None and expected != counts[k]:
            failures.append('USER_COUNT:'+k)
    actual_types = {by[i]['ending_type'] for i in terminals}
    if actual_types & set(policy['forbidden_endings']):
        failures.append('USER_ENDING_FORBIDDEN')
    check('ending_types', set(policy['required_endings']) <= actual_types,
          {k: [i for i in terminals if by[i]['ending_type'] == k] for k in sorted(ENDINGS)})
    check('small', 'small' in actual_types, [i for i in terminals if by[i]['ending_type'] == 'small'],
          required=policy['long_story'] and not policy['ending_override'])
    crossings, simple_merges = [], []
    for c in choices:
        for a, b in combinations(succ[c], 2):
            if by[a]['kind'] != 'scene' or by[b]['kind'] != 'scene':
                continue
            for m in order:
                if by[m]['kind'] != 'scene' or len(prev[m]) < 2 or m in (a, b):
                    continue
                if m in reach[a] & reach[b]:
                    paths = disjoint_paths(a, b, m, succ)
                    if paths:
                        # A nested decision must occur before this merge, on a
                        # private arm, not elsewhere downstream in the graph.
                        arm_choices = [[q for q in choices if q in reach[t] and
                                        q not in reach[other] and m in reach[q]]
                                       for t, other in ((a, b), (b, a))]
                        # Verify that the deep arm can actually take part in
                        # two independent paths; a detour into an earlier common
                        # bottleneck cannot lend depth to an unrelated bypass.
                        arm_choices = [[q for q in qs if disjoint_paths(q, other, m, succ)]
                                       for qs, other in zip(arm_choices, (b, a))]
                        if all(arm_choices):
                            pairs = [(q, r) for q in arm_choices[0] for r in arm_choices[1]
                                     if disjoint_paths(q, r, m, succ)]
                            if not pairs:
                                arm_choices[1] = []
                        evidence = {'choice': c, 'merge': m, 'paths': paths,
                                    'arms': [a, b], 'arm_choices': arm_choices}
                        if any(arm_choices):
                            evidence['shape'] = 'double_wing' if all(arm_choices) else 'single_deep'
                            crossings.append(evidence)
                        else:
                            simple_merges.append(evidence)
    check('crossing', bool(crossings), crossings, required=policy['long_story'])
    woven = []
    wings = [x for x in crossings if x['shape'] == 'double_wing']
    for x, y in combinations(wings, 2):
        m, n = x['merge'], y['merge']
        if x['choice'] != y['choice'] or x['arms'] != y['arms'] or m in reach[n] or n in reach[m]:
            continue
        joins = [j for j in order if by[j]['kind'] == 'scene' and j in reach[m] & reach[n]]
        if joins:
            woven.append({'choice': x['choice'], 'shared_stages': [m, n], 'converges': joins[0]})
    check('woven', bool(woven), woven, required=policy['long_story'])
    check('branch_shapes', bool(crossings),
          {'single_deep': [x for x in crossings if x['shape'] == 'single_deep'],
           'double_wing': wings, 'woven': woven, 'simple_merges': simple_merges}, required=False)
    depths, nested = {}, {}
    for c in choices:
        ancestors = [a for a in choices if a != c and a in depths and
                     0 < sum(c in reach[t] for t in succ[a]) < len(succ[a])]
        parent = max(ancestors, key=lambda a: depths[a], default=None)
        depths[c] = 1 + (depths[parent] if parent else 0)
        nested[c] = (nested[parent] if parent else []) + [c]
    deepest = max(choices, key=lambda c: depths[c], default=None)
    check('depth', bool(deepest) and depths[deepest] >= 2,
          {'depth': depths.get(deepest, 0), 'choices': nested.get(deepest, [])}, required=policy['long_story'])
    # Empty choices, option menus and instant merges cannot masquerade as development.
    invalid_options = [c for c in choices if any(by[t]['kind'] == 'choice' for t in succ[c])]
    check('immediate_result', not invalid_options, invalid_options)
    major = {i for i in terminals if by[i]['ending_type'] != 'small'}
    locks = {i: [] for i in major}
    for c in choices:
        if len(ends[c] & major) < 2:
            continue
        for t in succ[c]:
            selected = ends[t] & major
            if len(selected) == 1:
                locks[next(iter(selected))].append(c)
    distinct = set().union(*(set(v) for v in locks.values()))
    check('ending_distribution', all(locks.values()) and len(distinct) >= 2, locks,
          required=len(major) >= 3)
    progressive = []
    for c in choices:
        for a, b in combinations(succ[c], 2):
            for stop, onward in ((a, b), (b, a)):
                if all(by[e]['ending_type'] == 'expected' for e in ends[stop]) and \
                   by[onward]['kind'] == 'scene' and any(by[e]['ending_type'] == 'main' for e in ends[onward]):
                    progressive.append({'choice': c, 'expected_arm': stop, 'true_arm': onward})
    check('progressive_ending', bool(progressive), progressive, required=False)
    # Count continued decisions, not extra leaves or the number of full paths.
    live_arms = {c: [t for t in succ[c] if by[t]['kind'] == 'scene' and
                    any(q in reach[t] for q in choices)] for c in choices}
    next_decision = {}
    for i in reversed(order):
        next_decision[i] = i if by[i]['kind'] == 'choice' else (
            next_decision[succ[i][0]] if succ[i] else None)
    growing = [c for c in choices if len({next_decision[t] for t in live_arms[c]}) >= 2]
    growth_paths = {}
    for c in growing:
        parents = [p for p in growing if p in growth_paths and c in reach[p]]
        parent = max(parents, key=lambda p: len(growth_paths[p]), default=None)
        growth_paths[c] = (growth_paths[parent] if parent else []) + [c]
    growth_path = max(growth_paths.values(), key=len, default=[])
    check('sustained_growth', len(growing) >= 4 and len(growth_path) >= 3,
          {'choices': growing, 'arms': {c: live_arms[c] for c in growing},
           'next_decisions': {c: [next_decision[t] for t in live_arms[c]] for c in growing},
           'successive_choices': growth_path, 'minimum_choices': 4, 'minimum_stages': 3},
          required=policy['long_story'])

    # Two distinct stopping levels with actual story between them. Terminal
    # endings still have no outgoing edges; continuation uses narrative scenes.
    ladders = []
    for first in progressive:
        for second in progressive:
            if first['choice'] == second['choice'] or second['choice'] not in reach[first['true_arm']]:
                continue
            a, b = ends[first['expected_arm']], ends[second['expected_arm']]
            if a.isdisjoint(b):
                ladders.append({'choices': [first['choice'], second['choice']],
                                'between_scene': first['true_arm'],
                                'expected_endings': [sorted(a), sorted(b)],
                                'continues_scene': second['true_arm']})
    check('ending_ladder', bool(ladders), ladders, required=policy['long_story'])

    # Legitimate stopping levels and the final resolution may end a route.
    # Elsewhere, at least two thirds of options must lead to more decisions;
    # stretching an immediate failure into a linear chain cannot evade this.
    settlement = {p['choice'] for p in progressive}
    active = [c for c in choices if live_arms[c] and c not in settlement]
    option_total = sum(len(succ[c]) for c in active)
    continuing = sum(len(live_arms[c]) for c in active)
    check('continuation_balance', bool(option_total) and continuing * 3 >= option_total * 2,
          {'choices': active, 'continuing_options': continuing, 'options': option_total,
           'settlement_choices': sorted(settlement),
           'closing_choices': [c for c in choices if not live_arms[c]]},
          required=policy['long_story'])
    return {'status': 'FAIL' if failures else 'PASS', 'failures': failures, 'checks': checks,
            'counts': counts, 'path_count': count, 'option_count': sum(len(succ[c]) for c in choices),
            'order': order}


def paths(plan):
    by, succ, prev, order, *_ = structure(plan)
    def walk(i, prefix):
        p = prefix + [i]
        if not succ[i]:
            yield p
        else:
            for j in succ[i]:
                yield from walk(j, p)
    yield from walk(order[0], [])
