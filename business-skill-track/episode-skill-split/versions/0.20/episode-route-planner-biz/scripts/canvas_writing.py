#!/usr/bin/env python3
"""Read-only canvas projection and one-batch editing acknowledgements.

This accepts writing material only after the edited canvas passes connectivity checks.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from route_contract import digest, node_hash, route_hash, MATERIAL_FIELDS


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def snapshot(current):
    if current.get('schema_version') != 'nextplay.route.v1':
        raise ValueError('CURRENT_CANVAS_SCHEMA_ERROR')
    project = current['identity']['story_id']
    data = current['data']
    nodes = data['nodes']
    refs = [n['node_ref'] for n in nodes]
    if len(set(refs)) != len(refs):
        raise ValueError('DUPLICATE_NODE_REF')
    # Exclude generated screenplay/media and presentation-only metadata.
    projected = []
    for n in nodes:
        content = n.get('content') or {}
        interaction = n.get('interaction') or {}
        projected.append({
            'node_ref': n['node_ref'], 'node_type': n['node_type'],
            'title': n.get('title'), 'summary': n.get('summary'),
            'content': {k: content.get(k) for k in ('conflict', 'objective', 'mood')},
            'question': interaction.get('question'),
            'assets': n.get('assets'), 'conditions': n.get('conditions'),
            'effects': n.get('effects'),
            'ending': {k: (n.get('metadata') or {}).get(k) for k in ('is_ending', 'ending_type')},
        })
    edges = [{k: e.get(k) for k in (
        'edge_ref', 'source_node_ref', 'target_node_ref', 'edge_type',
        'choice', 'conditions', 'effects', 'priority')}
        for e in data['edges']]
    edge_refs = [e['edge_ref'] for e in edges]
    if len(edge_refs) != len(set(edge_refs)):
        raise ValueError('DUPLICATE_EDGE_REF')
    return {'project_id': project, 'route_ref': data['route_ref'],
            'entry': data.get('entry_node_ref'),
            'nodes': sorted(projected, key=lambda n: n['node_ref']),
            'edges': sorted(edges, key=lambda e: e['edge_ref'])}


def fingerprint(current):
    return digest(snapshot(current))


def graph_issues(current):
    data = current['data']
    nodes = {n['node_ref']: n for n in data['nodes']}
    adj = {ref: [] for ref in nodes}
    issues = []
    entry = data.get('entry_node_ref')
    if entry not in nodes or nodes.get(entry, {}).get('node_type') != 'video':
        issues.append('入口剧集不存在')
    for e in data['edges']:
        source, target = e['source_node_ref'], e['target_node_ref']
        if source not in nodes or target not in nodes:
            issues.append('连线目标不存在:' + e['edge_ref'])
        else:
            adj[source].append(target)
    for ref, n in nodes.items():
        if n['node_type'] == 'choice' and len(set(adj[ref])) < 2:
            issues.append('选择不足两个有效方向:' + ref)
        if n['node_type'] == 'video' and len(set(adj[ref])) > 1:
            issues.append('剧集存在多个默认后继:' + ref)
        if n['node_type'] == 'video' and not adj[ref] and not (n.get('metadata') or {}).get('is_ending'):
            issues.append('非结局剧集缺少后续:' + ref)
    seen, active = set(), set()
    def walk(ref):
        if ref in active:
            issues.append('存在循环:' + ref); return
        if ref in seen: return
        seen.add(ref); active.add(ref)
        for target in adj[ref]: walk(target)
        active.remove(ref)
    if entry in nodes: walk(entry)
    if set(nodes) - seen:
        issues.append('画布上孤立的剧集或选择:' + ','.join(sorted(set(nodes) - seen)))
    return issues


def observe(current, state):
    snap = snapshot(current)
    same_project = state.get('project_id') == snap['project_id'] and state.get('policy') == 'delete-then-repair-v1'
    previous = state.get('snapshot') if same_project else None
    old = {n['node_ref']: n for n in (previous or {}).get('nodes', [])}
    new = {n['node_ref']: n for n in snap['nodes']}
    return {'project_id': snap['project_id'], 'fingerprint': digest(snap),
            'ask_user': not same_project or state.get('fingerprint') != digest(snap) or (state.get('action') == 'stop' and bool(graph_issues(current))),
            'graph_issues': graph_issues(current),
            'has_previous': previous is not None,
            'added': sorted(new.keys() - old.keys()) if previous else [],
            'deleted': sorted(old.keys() - new.keys()) if previous else [],
            'changed': sorted(k for k in old.keys() & new.keys() if old[k] != new[k]),
            'edges_changed': bool(previous and previous['edges'] != snap['edges'])}


def confirm(current, expected, action):
    snap = snapshot(current)
    if digest(snap) != expected:
        raise ValueError('CANVAS_CHANGED_SINCE_QUESTION')
    if action not in {'direct', 'transition', 'stop', 'record'}:
        raise ValueError('INVALID_EDIT_DECISION')
    if action == 'record' and graph_issues(current):
        raise ValueError('CURRENT_GRAPH_REPAIR_REQUIRED')
    return {'policy': 'delete-then-repair-v1', 'project_id': snap['project_id'], 'fingerprint': expected,
            'action': action, 'snapshot': snap}


def build(current, state, target, material):
    observation = observe(current, state)
    if observation['ask_user']:
        raise ValueError('EDIT_CONFIRMATION_REQUIRED')
    if state.get('action') in {'direct', 'transition'}:
        raise ValueError('COMPLETE_AUTHORIZED_REPAIR_THEN_RECORD_READBACK')
    issues = graph_issues(current)
    if issues:
        raise ValueError('CURRENT_GRAPH_REPAIR_REQUIRED: ' + '; '.join(issues))
    data = current['data']
    by_id = {n['node_ref']: n for n in data['nodes']}
    if target not in by_id or by_id[target]['node_type'] != 'video':
        raise ValueError('TARGET_EPISODE_MISSING')
    if set(material) != MATERIAL_FIELDS:
        raise ValueError('TARGET_MATERIAL_FIELDS_ERROR')
    for key in ('单集梗概', '本集冲突', 'stop_boundary'):
        if not isinstance(material[key], str) or not material[key].strip():
            raise ValueError('TARGET_MATERIAL_EMPTY:' + key)
    for key in ('entry_state', 'state_changes'):
        if not isinstance(material[key], dict):
            raise ValueError('TARGET_STATE_NOT_OBJECT')
    for key in ('allowed_characters', 'allowed_scenes', 'allowed_props'):
        value = material[key]
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value) or len(set(value)) != len(value):
            raise ValueError('TARGET_ASSET_LIST_INVALID')
    pressure = material['entry_state'].get('dramatic_pressure')
    effect = material['state_changes'].get('dramatic_effect')
    if (pressure is None) != (effect is None):
        raise ValueError('TARGET_DRAMATIC_PAIR_INCOMPLETE')
    valid = data['edges']
    incoming = {k: [] for k in by_id}
    outgoing = {k: [] for k in by_id}
    for e in valid:
        outgoing[e['source_node_ref']].append(e)
        incoming[e['target_node_ref']].append(e)
    nodes, choices, endings = [], [], []
    for ref, n in by_id.items():
        outs = outgoing[ref]
        is_choice = n['node_type'] == 'choice'
        # The graph guard has already rejected missing targets and incomplete choices.
        options = [{'选项编号': e['edge_ref'], '选项文字': (e.get('choice') or {}).get('label') or '',
                    '目标分集编号': e['target_node_ref']} for e in outs if e['edge_type'] == 'choice']
        has_choice = is_choice and len({o['目标分集编号'] for o in options}) >= 2
        if has_choice and any(not o['选项文字'] for o in options):
            raise ValueError('CONNECTED_CHOICE_LABEL_MISSING')
        meta = n.get('metadata') or {}
        content = n.get('content') or {}
        m = {'单集梗概': n.get('summary') or n.get('title') or ref,
             '本集冲突': content.get('conflict') or n.get('summary') or n.get('title') or ref,
             'entry_state': {}, 'state_changes': {}, 'allowed_characters': [],
             'allowed_scenes': [], 'allowed_props': [],
             'stop_boundary': content.get('objective') or meta.get('stop_boundary') or '止于本集当前事件，不演出后续。'}
        if ref == target:
            m = deepcopy(material)
        node = {'node_id': ref, 'node_type': 'episode', '分集标题': n.get('title') or ref,
                'route_material': m,
                '前置节点编号列表': list(dict.fromkeys(e['source_node_ref'] for e in incoming[ref])),
                '后续节点编号列表': list(dict.fromkeys(e['target_node_ref'] for e in outs)),
                '是否结局': bool(meta.get('is_ending')), 'ending_type': meta.get('ending_type'),
                '互动节点': {'是否为分支节点': has_choice, '是否有选择问题': has_choice,
                    '选择问题': (n.get('interaction') or {}).get('question') or '' if has_choice else '',
                    '选项列表': options if has_choice else [],
                    '默认下一分集编号': outs[0]['target_node_ref'] if len(outs) == 1 else '无'}}
        node['node_route_material_hash'] = node_hash(node)
        nodes.append(node)
        choices.extend({'source_node_id': ref, **o} for o in (options if has_choice else []))
        if node['是否结局']:
            endings.append({'node_id': ref, 'ending_type': node['ending_type']})
    fp = observation['fingerprint']
    route = {'contract_version': 'nextplay.episode-route-handoff.v1',
             'capability_id': 'episode-route-planner-biz',
             'project_id': current['identity']['story_id'], 'route_id': data['route_ref'],
             'route_version': 'canvas-write-' + fp[:16] + '-' + target,
             'route_status': 'accepted', 'route_input_hash': fp,
             'accepted_at': datetime.now(timezone.utc).isoformat(),
             'nodes': nodes,
             'edges': [{'edge_id': e['edge_ref'], 'source_node_id': e['source_node_ref'],
                        'target_node_id': e['target_node_ref'], 'edge_type': e['edge_type']} for e in valid],
             'choices': choices, 'endings': endings}
    route['route_output_hash'] = route_hash(route)
    receipt = {'contract_version': 'nextplay.canvas-node-writing.v1',
               'acceptance_scope': 'current_node_writing_material_only',
               'project_id': route['project_id'], 'node_ref': target,
               'canvas_fingerprint': fp, 'observed_revision': current['revision'],
               'route_output_hash': route['route_output_hash'],
               'excluded_dangling_edge_refs': [e['edge_ref'] for e in data['edges'] if e not in valid],
               'graph_planning_accepted': False}
    return route, receipt


def verify(current, route, receipt):
    if fingerprint(current) != receipt['canvas_fingerprint'] or current['identity']['story_id'] != receipt['project_id']:
        raise ValueError('CURRENT_CANVAS_CHANGED_REBUILD_NODE_MATERIAL')
    if route_hash(route) != receipt['route_output_hash'] or route.get('route_output_hash') != receipt['route_output_hash']:
        raise ValueError('WRITING_SNAPSHOT_CHANGED')
    if any(n.get('node_route_material_hash') != node_hash(n) for n in route['nodes']):
        raise ValueError('WRITING_NODE_MATERIAL_CHANGED')
    if receipt['node_ref'] not in {n['node_ref'] for n in current['data']['nodes']}:
        raise ValueError('TARGET_EPISODE_MISSING')
    return {'status': 'CURRENT_NODE_MATERIAL_VALID', 'node_ref': receipt['node_ref'],
            'current_revision': current['revision']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('observe', 'record', 'confirm', 'build'):
        p = sub.add_parser(command); p.add_argument('current'); p.add_argument('state')
        if command == 'confirm': p.add_argument('expected'); p.add_argument('action', choices=['direct','transition','stop'])
        if command == 'build': p.add_argument('target'); p.add_argument('material'); p.add_argument('out')
    p = sub.add_parser('verify'); p.add_argument('current'); p.add_argument('out')
    args = parser.parse_args(); current = read(args.current)
    if args.command == 'verify':
        out = Path(args.out); result = verify(current, read(out/'writing-route.json'), read(out/'canvas-writing-receipt.json'))
    elif args.command in {'record', 'confirm'}:
        result = confirm(current, getattr(args, 'expected', fingerprint(current)), getattr(args, 'action', 'record'))
        save(args.state, result); result = {k:v for k,v in result.items() if k != 'snapshot'}
    else:
        state = read(args.state) if Path(args.state).exists() else {}
        if args.command == 'observe': result = observe(current, state)
        else:
            route, receipt = build(current, state, args.target, read(args.material))
            out = Path(args.out); save(out/'writing-route.json',route); save(out/'canvas-writing-receipt.json',receipt)
            result = receipt
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    try: main()
    except (ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error))
