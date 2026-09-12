"""0.20: frozen mainline, scoped branch repair, graph inspection and exact story projection."""
import argparse
import hashlib
import json
import os
import re
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import graph_check as graph
import route_contract as handoff
from user_constraints import parse_explicit_counts


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def policy(root):
    text = (root/'user-request.md').read_text()
    brief = read(root/'brief.json')
    counts = parse_explicit_counts(text)
    minutes = brief['duration_minutes']
    if isinstance(minutes, bool) or not isinstance(minutes, (int, float)) or minutes <= 0:
        raise ValueError('INPUT: duration_minutes must be positive; classification only')
    mentioned = {float(x) for x in re.findall(r'(\d+(?:\.\d+)?)\s*分钟', text)}
    if len(mentioned) == 1 and minutes != next(iter(mentioned)):
        raise ValueError('USER_CONSTRAINT: duration differs from explicit user duration')
    overrides = brief.get('user_overrides', {})
    exemptions = {}
    allowed_rules = {'small', 'crossing', 'woven', 'depth', 'ending_types', 'ending_distribution',
                     'immediate_result', 'sustained_growth', 'ending_ladder', 'continuation_balance'}
    for item in overrides.get('exemptions', []):
        if item['rule'] not in allowed_rules or not item.get('reason') or not item.get('quote') or item['quote'] not in text:
            raise ValueError('USER_CONSTRAINT: each default exemption needs an exact user quote and reason')
        exemptions[item['rule']] = item
    required = overrides.get('required_endings')
    forbidden = overrides.get('forbidden_endings', [])
    if required is not None or forbidden:
        quote = overrides.get('ending_quote', '')
        if not quote or quote not in text:
            raise ValueError('USER_CONSTRAINT: ending override requires original user quote')
    if required is not None and (not isinstance(required, list) or not set(required) <= graph.ENDINGS):
        raise ValueError('USER_CONSTRAINT: invalid required endings')
    if not isinstance(forbidden, list) or not set(forbidden) <= graph.ENDINGS:
        raise ValueError('USER_CONSTRAINT: invalid forbidden endings')
    ending_override = required is not None or bool(forbidden)
    if required is None:
        required = sorted(graph.ENDINGS-set(forbidden))
        if counts['ending_count'] is not None and counts['ending_count'] < len(required):
            required = []
    if set(required) & set(forbidden) or (counts['ending_count'] is not None and len(required) > counts['ending_count']):
        raise ValueError('USER_CONSTRAINT: contradictory ending requirements')
    if counts['choice_node_count'] == 0:
        if counts['ending_count'] not in (None, 1):
            raise ValueError('USER_CONSTRAINT: no choices cannot reach multiple distinct endings')
        required = overrides.get('required_endings', [])
        if len(required) > 1:
            raise ValueError('USER_CONSTRAINT: no choices conflicts with multiple ending types')
        for key in ('small', 'crossing', 'woven', 'depth', 'ending_distribution',
                    'sustained_growth', 'ending_ladder', 'continuation_balance'):
            exemptions[key] = {'reason': 'user explicitly requires no choices', 'quote': text}
    return {'hard_counts': counts, 'duration_minutes': minutes, 'long_story': minutes >= 15,
            'required_endings': required, 'forbidden_endings': forbidden,
            'ending_override': ending_override, 'exemptions': exemptions}


def story_parts(story):
    parts = story['episodes']
    if not isinstance(parts, list) or not parts or not isinstance(story['complete_story'], str):
        raise ValueError('INPUT: story needs complete_story and episodes')
    by = {}
    for part in parts:
        for key in ('id', 'title', 'text', 'conflict', 'stop_boundary'):
            if not isinstance(part.get(key), str) or not part[key].strip():
                raise ValueError('INPUT: missing story slice field '+key)
        if part['id'] in by:
            raise ValueError('INPUT: duplicate story slice ID')
        by[part['id']] = part
    # Identity of the projection, not a literary quality judgement.
    clean = lambda s: re.sub(r'\s+', '', s)
    if clean(''.join(p['text'] for p in parts)) != clean(story['complete_story']):
        raise ValueError('PROJECTION: slices must cover their complete story without rewriting or omission')
    return by


def freeze(root):
    if (root/'mainline-lock.json').exists():
        return frozen(root)
    value = policy(root)
    source = (root/'mainline-story.md').read_text(encoding='utf-8')
    story = read(root/'mainline.json')
    story_parts(story)
    if not source.strip() or re.sub(r'\s+', '', source) != re.sub(r'\s+', '', story['complete_story']):
        raise ValueError('PROJECTION: mainline slices must preserve the independently written mainline-story.md')
    lock = {'contract_version': 'route-020.mainline-lock.v1', 'created_at': stamp(), 'policy': value,
            'files': {name: sha(root/name) for name in ('user-request.md', 'brief.json', 'mainline-story.md', 'mainline.json')}}
    write(root/'mainline-lock.json', lock)
    return lock


def frozen(root):
    lock = read(root/'mainline-lock.json')
    if any(sha(root/n) != h for n, h in lock['files'].items()):
        raise ValueError('MAINLINE_LOCK: frozen input changed; do not repair the mainline')
    if lock['policy'] != policy(root):
        raise ValueError('MAINLINE_LOCK: compiled policy differs')
    return lock


def sources(root, branches):
    main = read(root/'mainline.json')
    main_parts = story_parts(main)
    by = dict(main_parts)
    for story in branches['stories']:
        for key, part in story_parts(story).items():
            if key in by:
                raise ValueError('PROJECTION: duplicated source ID '+key)
            by[key] = part
    return main_parts, by


def validate_bundle(root, bundle):
    plan, branches = bundle['plan'], bundle['branches']
    by, succ, prev, order, *_ = graph.structure(plan)
    main, all_parts = sources(root, branches)
    path = plan['mainline_path']
    if not path or path[0] != order[0] or len(path) != len(set(path)):
        raise ValueError('MAINLINE_LOCK: invalid mainline path')
    if any(a not in succ or b not in succ[a] for a, b in zip(path, path[1:])):
        raise ValueError('MAINLINE_LOCK: mainline path not contiguous')
    if by[path[-1]]['kind'] != 'ending':
        raise ValueError('MAINLINE_LOCK: mainline must reach an ending')
    source_order = [by[i]['source'] for i in path if by[i]['kind'] != 'choice']
    if source_order != list(main):
        raise ValueError('MAINLINE_LOCK: mainline episodes must occur exactly in frozen story order')
    used = [n['source'] for n in by.values() if n['kind'] != 'choice']
    if len(used) != len(set(used)) or set(used) != set(all_parts):
        raise ValueError('PROJECTION: every story slice maps to exactly one narrative episode')
    return by, all_parts


def current(root):
    frozen(root)
    state = read(root/'topology-state.json')
    if state['hash'] != handoff.digest(state['bundle']):
        raise ValueError('RECEIPT: topology state hash mismatch')
    return state


def submit(root, submission):
    lock = frozen(root)
    old = current(root) if (root/'topology-state.json').exists() else None
    if submission.get('expected_hash') != (old['hash'] if old else None):
        raise ValueError('STALE: read current topology hash before repair')
    bundle = {'plan': submission['plan'], 'branches': submission['branches']}
    by, parts = validate_bundle(root, bundle)
    if old:
        old_by, old_parts = validate_bundle(root, old['bundle'])
        path = old['bundle']['plan']['mainline_path']
        if bundle['plan']['mainline_path'] != path or any(by.get(i) != old_by[i] for i in path):
            raise ValueError('MAINLINE_LOCK: repair changed frozen mainline nodes or choices')
        changed = {i for i in set(old_by)|set(by) if old_by.get(i) != by.get(i)}
        for i, n in by.items():
            if n['kind'] != 'choice' and parts[n['source']] != old_parts.get(n['source']):
                changed.add(i)
        if not changed <= set(submission.get('affected_nodes', [])) or not submission.get('reason', '').strip():
            raise ValueError('REPAIR_SCOPE: name every changed node and the actual problem')
        if old['hash'] == handoff.digest(bundle):
            return old
        write(root/'history'/f"revision-{old['revision']:03d}.json", old)
    elif not (root/'exploration.md').is_file():
        raise ValueError('INPUT: missing discarded shape exploration')
    report = graph.inspect(bundle['plan'], lock['policy'])
    if old:
        prior = graph.inspect(old['bundle']['plan'], lock['policy'])
        regressed = [k for k, v in prior['checks'].items() if v['status'] == 'PASS' and report['checks'][k]['status'] == 'FAIL']
        if regressed:
            raise ValueError('REPAIR_REGRESSION: repair broke passed checks '+','.join(regressed))
    state = {'contract_version': 'route-020.topology.v1', 'revision': old['revision']+1 if old else 1,
             'hash': handoff.digest(bundle), 'bundle': bundle, 'reason': submission.get('reason', 'initial graph'),
             'affected_nodes': submission.get('affected_nodes', []), 'created_at': stamp(), 'graph_report': report}
    write(root/'topology-state.json', state)
    # Derived records are invalidated by their hash binding, not by rewriting upstream files.
    return state


def materialize(root, state):
    bundle = state['bundle']
    by, parts = validate_bundle(root, bundle)
    _, succ, prev, order, *_ = graph.structure(bundle['plan'])
    mapping = {i: f'episode-{index:03d}' for index, i in enumerate(order, 1)}
    nodes = []
    for i in order:
        n = by[i]
        choice = n['kind'] == 'choice'
        if choice:
            part = {'title': n['question'], 'text': n['question'], 'conflict': n['question'],
                    'stop_boundary': '只显示选择，选项尚未执行。'}
        else:
            part = parts[n['source']]
        material = {'单集梗概': part['text'], '本集冲突': part['conflict'],
                    'entry_state': part.get('entry_state', {}), 'state_changes': part.get('state_changes', {}),
                    'allowed_characters': part.get('characters', []), 'allowed_scenes': part.get('scenes', []),
                    'allowed_props': part.get('props', []), 'stop_boundary': part['stop_boundary']}
        nxt = [mapping[j] for j in succ[i]]
        options = [{'选项编号': f'option-{k:03d}', '选项文字': o['text'], '目标分集编号': mapping[o['target']]}
                   for k, o in enumerate(n['options'], 1)] if choice else []
        nodes.append({'node_id': mapping[i], 'node_type': 'episode', '分集标题': part['title'],
                      'route_material': material, '前置节点编号列表': [mapping[j] for j in prev[i]],
                      '后续节点编号列表': nxt, '是否结局': n['kind']=='ending',
                      'ending_type': n.get('ending_type'), '互动节点': {'是否为分支节点': choice,
                      '是否有选择问题': choice, '选择问题': n['question'] if choice else '', '选项列表': options,
                      '默认下一分集编号': nxt[0] if nxt else '无'}, 'node_route_material_hash': ''})
    edges, choices, endings = handoff.expected_indexes(nodes)
    brief = read(root/'brief.json')
    route = {'contract_version': handoff.CONTRACT_VERSION, 'capability_id': handoff.CAPABILITY_ID,
             'project_id': brief['project_id'], 'route_id': brief.get('route_id', 'route-020'),
             'route_version': str(state['revision']), 'route_status': 'draft',
             'route_input_hash': handoff.digest(frozen(root)['files']), 'route_output_hash': '', 'accepted_at': None,
             'nodes': nodes, 'edges': edges, 'choices': choices, 'endings': endings}
    errors = handoff.validate(route, require_accepted=False)
    if errors:
        raise ValueError('CONTRACT: '+';'.join(errors))
    return route, mapping


def check(root):
    state = current(root)
    report = graph.inspect(state['bundle']['plan'], frozen(root)['policy'])
    route, mapping = materialize(root, state)
    report.update(topology_hash=state['hash'], revision=state['revision'], node_id_map=mapping)
    write(root/'graph-report.json', report)
    write(root/'route-candidate.json', route)
    return report


def accept(root, output=None):
    report = check(root)
    if report['status'] != 'PASS':
        raise ValueError('GRAPH_REPAIR_REQUIRED: '+','.join(report['failures']))
    receipt = {'contract_version': 'route-020.planning.v1', 'status': 'PLANNING_ACCEPTED',
               'accepted_at': stamp(), 'scope': 'graph-and-projection-only; plot is author responsibility',
               'files': {n: sha(root/n) for n in ('mainline-lock.json', 'topology-state.json', 'graph-report.json', 'route-candidate.json')}}
    write(root/'planning-acceptance.json', receipt)
    if output:
        write(output, handoff.seal(read(root/'route-candidate.json')))
    return receipt


def verify(root):
    receipt = read(root/'planning-acceptance.json')
    if receipt.get('status') != 'PLANNING_ACCEPTED' or any(sha(root/n) != h for n, h in receipt['files'].items()):
        raise ValueError('RECEIPT: accepted files changed')
    report = graph.inspect(current(root)['bundle']['plan'], frozen(root)['policy'])
    route, _ = materialize(root, current(root))
    if report['status'] != 'PASS' or route != read(root/'route-candidate.json'):
        raise ValueError('RECEIPT: current graph or projection differs')
    return receipt


def status(root):
    names = ('user-request.md', 'brief.json', 'mainline.json') if (root/'mainline-lock.json').exists() else (
        'user-request.md', 'brief.json', 'mainline-story.md', 'mainline.json')
    for name in names:
        if not (root/name).exists():
            return {'next': 'WRITE_INPUT', 'file': name}
    if not (root/'mainline-lock.json').exists():
        return {'next': 'FREEZE_MAINLINE'}
    frozen(root)
    if not (root/'topology-state.json').exists():
        return {'next': 'WRITE_BRANCH_STORIES_AND_SUBMIT_GRAPH'}
    state = current(root)
    report = graph.inspect(state['bundle']['plan'], frozen(root)['policy'])
    return {'next': 'AUTHOR_READ_THROUGH_THEN_ACCEPT' if report['status']=='PASS' else 'REPAIR_FAILED_BRANCHES',
            'expected_hash': state['hash'], 'report': report}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['freeze', 'submit', 'check', 'accept', 'verify', 'status', 'paths'])
    p.add_argument('cache_root', type=Path)
    p.add_argument('file', nargs='?', type=Path)
    args = p.parse_args()
    root = args.cache_root.resolve()
    try:
        if args.action == 'submit':
            result = submit(root, read(args.file))
            result = {'hash': result['hash'], 'revision': result['revision'], 'graph_report': result['graph_report']}
        elif args.action == 'paths':
            for path in graph.paths(current(root)['bundle']['plan']):
                print(json.dumps(path, ensure_ascii=False))
            return 0
        elif args.action == 'accept':
            result = accept(root, args.file)
        else:
            result = globals()[args.action](root)
        report = result.get('graph_report', result)
        if report.get('status') == 'FAIL':
            result = {**result, 'status': 'NEEDS_REPAIR', 'next': 'REPAIR_FAILED_BRANCHES',
                      'graph_report': report, 'accepted': False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.action in ('accept', 'verify'):
            print('PLANNING_ACCEPTED')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        # Only known candidate-validation failures are normal author iteration.
        # Missing/corrupt files, locks, receipts and unexpected exceptions remain errors.
        code = str(error).partition(':')[0]
        if (isinstance(error, ValueError) and args.action != 'verify'
                and code in {'STRUCTURE', 'PROJECTION', 'GRAPH_REPAIR_REQUIRED', 'REPAIR_REGRESSION'}):
            print(json.dumps({'status': 'NEEDS_REPAIR', 'accepted': False,
                              'next': 'REPAIR_FAILED_BRANCHES', 'code': code,
                              'issues': [str(error)]}, ensure_ascii=False))
            return 0
        print(json.dumps({'status': 'FAIL', 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
