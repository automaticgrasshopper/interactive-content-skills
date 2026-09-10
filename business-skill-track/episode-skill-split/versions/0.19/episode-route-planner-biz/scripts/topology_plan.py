#!/usr/bin/env python3
"""Freeze a planned graph, derive paths and project synopses without back-writing it."""
from __future__ import annotations
import argparse
from copy import deepcopy
from pathlib import Path
import route_growth as legacy

UPSTREAM_FILES = (*legacy.UPSTREAM_FILES, 'story-treatment.json')
DERIVED = ('route-ledger.json', 'topology-review-A.json', 'topology-review-B.json',
           'episode-synopses.json', 'route-candidate.json', 'synopsis-review.json',
           'emotional-spine.json', 'planning-acceptance.json')
read = legacy._read
digest = legacy.digest
write = legacy._atomic


def sources(root):
    hashes, values, identity = legacy._upstream(root)
    hashes['story-treatment.json'] = legacy.hashlib.sha256((root / 'story-treatment.json').read_bytes()).hexdigest()
    treatment = read(root / 'story-treatment.json')
    if not isinstance(treatment, dict) or not isinstance(treatment.get('choices'), list):
        raise ValueError('支线事实登记需要choices数组')
    return hashes, values, identity


def project(root, plan):
    _, values, identity = sources(root)
    legacy._keys(plan, {'nodes', 'edges'}, '正式拓扑计划')
    nodes, edges = plan['nodes'], plan['edges']
    if not isinstance(nodes, list) or not nodes or not isinstance(edges, list):
        raise ValueError('拓扑需要非空nodes和edges数组')
    ids = set()
    for n in nodes:
        if not isinstance(n, dict):
            raise ValueError('节点必须为对象')
        legacy._text(n.get('node_id'), '临时节点ID')
        if n['node_id'] in ids:
            raise ValueError('临时节点ID重复')
        ids.add(n['node_id'])
        legacy._node({k:v for k,v in n.items() if k != 'node_id'}, *legacy._references(values))
    for e in edges:
        legacy._keys(e, {'source_node_id','target_node_id','option_index'}, '边')
        if e['source_node_id'] not in ids or e['target_node_id'] not in ids:
            raise ValueError('边引用不存在节点')
    for n in nodes:
        out = [e for e in edges if e['source_node_id'] == n['node_id']]
        indexes = [e['option_index'] for e in out]
        if n['kind'] == 'choice':
            if any(type(i) is not int for i in indexes) or sorted(indexes) != list(range(len(n['options']))):
                raise ValueError('每个选择选项必须恰好有一条边')
        elif indexes != ([] if n['kind'] == 'ending' else [None]):
            raise ValueError('普通节点须有唯一后继，结局无后继')
    state = {'nodes':nodes, 'edges':edges, 'frontiers':[], 'identity':identity,
             'upstream_hashes':sources(root)[0]}
    route, mapping = legacy._project(state)
    from planning_gate import validate_user_counts, validate_assets
    errors = []
    validate_user_counts(route, values['user-intent-lock.json'], errors)
    validate_assets(route, values['creative-brief.json'], errors)
    intent = values['user-intent-lock.json']
    if intent.get('shape_mode') == 'exact':
        from shape_lock import shape_lock_issues, route_satisfies_exact_lock
        errors.extend(shape_lock_issues(intent.get('locked_shape')))
        if not errors and not route_satisfies_exact_lock(route, intent['locked_shape']):
            errors.append('未兑现用户锁定形状')
    if errors:
        raise ValueError('；'.join(errors))
    # The mainline must be a directly connected complete route in source order.
    segments = values['mainline-decomposition.json']['mainline_segments']
    main = []
    for segment in segments:
        matches = [n['node_id'] for n in nodes if n.get('mainline_segment_id') == segment['segment_id']]
        if len(matches) != 1:
            raise ValueError('每个主线切片必须恰好映射一个节点')
        main.append(matches[0])
    if main[0] != nodes[0]['node_id'] or next(n for n in nodes if n['node_id']==main[-1])['kind'] != 'ending':
        raise ValueError('主线路径必须从入口到结局')
    for a,b in zip(main, main[1:]):
        if not any(e['source_node_id']==a and e['target_node_id']==b for e in edges):
            raise ValueError('主线切片必须按原文顺序直接相连')
    return route, mapping


def load(root):
    state = read(root / 'topology-state.json')
    legacy._keys(state, {'contract_version','upstream_hashes','revisions'}, '拓扑状态')
    if state['contract_version'] != 'nextplay.planned-topology.v1' or state['upstream_hashes'] != sources(root)[0]:
        raise ValueError('冻结上游变化；保留缓存，报告上游失效，不重建历史')
    if not isinstance(state['revisions'],list) or not state['revisions']:
        raise ValueError('缺少拓扑版本')
    previous = None
    for i, r in enumerate(state['revisions'],1):
        legacy._keys(r, {'index','previous_hash','reason','plan','hash'}, '拓扑修订')
        if r['index'] != i or r['previous_hash'] != previous or r['hash'] != digest({k:v for k,v in r.items() if k != 'hash'}):
            raise ValueError('拓扑修订链失效')
        previous = r['hash']
    project(root,state['revisions'][-1]['plan'])
    return state


def freeze(root, submission):
    root.mkdir(parents=True,exist_ok=True)
    legacy._keys(submission, {'expected_topology_hash','reason','plan'}, '拓扑提交')
    legacy._text(submission['reason'],'本次创建或局部修改原因')
    with legacy._lock(root):
        errors=[]
        from planning_gate import validate_upstream
        validate_upstream(root,errors)
        if errors:
            raise ValueError('；'.join(errors))
        state = load(root) if (root/'topology-state.json').exists() else {
            'contract_version':'nextplay.planned-topology.v1','upstream_hashes':sources(root)[0],'revisions':[]}
        previous = state['revisions'][-1]['hash'] if state['revisions'] else None
        if submission['expected_topology_hash'] != previous:
            raise ValueError('陈旧拓扑提交，先读取当前状态')
        project(root,submission['plan'])
        revision = {'index':len(state['revisions'])+1,'previous_hash':previous,
                    'reason':submission['reason'],'plan':submission['plan']}
        revision['hash']=digest(revision)
        if state['revisions']:
            old={n['node_id']:n for n in state['revisions'][-1]['plan']['nodes']}
            new={n['node_id']:n for n in submission['plan']['nodes']}
            changed=sorted(k for k in old.keys()|new.keys() if old.get(k)!=new.get(k))
        else:
            changed=[n['node_id'] for n in submission['plan']['nodes']]
        archive=root/'repair-history'/str(revision['index'])
        archive.mkdir(parents=True,exist_ok=True)
        # Archive all invalidated files before writing the new checkpoint.
        for name in DERIVED:
            if (root/name).exists():
                write(archive/name,read(root/name))
        state['revisions'].append(revision)
        write(root/'topology-state.json',state)
        for name in DERIVED:
            (root/name).unlink(missing_ok=True)
        return {'status':'TOPOLOGY_FROZEN','topology_hash':revision['hash'],'changed_node_ids':changed}


def current(root):
    state=load(root)
    plan=state['revisions'][-1]['plan']
    route,mapping=project(root,plan)
    return state,plan,route,mapping


def ledger(root):
    state,plan,route,mapping=current(root)
    byid={n['node_id']:n for n in route['nodes']}
    paths=[]
    def visit(nid,path,facts):
        if len(paths)>=10000:
            raise ValueError('路径超过10000，需扩大记账实现，不能截断后验收')
        n=byid[nid]; facts=deepcopy(facts)
        for key,required in n['route_material']['entry_state'].items():
            allowed=required['one_of'] if isinstance(required,dict) and set(required)=={'one_of'} else [required]
            if key not in facts or facts[key] not in allowed:
                raise ValueError(f'分支状态前提不满足：{path+[nid]} / {key}')
        facts.update(n['route_material']['state_changes'])
        path=path+[nid]
        if n['是否结局']:
            paths.append({'node_ids':path,'ending_id':nid,'ending_type':n['ending_type'],'exit_state':facts})
        for child in n['后续节点编号列表']:
            visit(child,path,facts)
    # Initial shared facts belong to the visible creative brief.
    initial=read(root/'creative-brief.json').get('initial_state',{})
    if not isinstance(initial,dict): raise ValueError('initial_state必须为对象')
    visit(route['nodes'][0]['node_id'],[],initial)
    main=sorted((n for n in plan['nodes'] if n.get('mainline_segment_id')),
                key=lambda n: [s['segment_id'] for s in read(root/'mainline-decomposition.json')['mainline_segments']].index(n['mainline_segment_id']))
    return {'topology_hash':state['revisions'][-1]['hash'],'node_id_map':mapping,
            'mainline_path':[mapping[n['node_id']] for n in main],
            'path_count':len(paths),'paths':paths,
            'merge_nodes':[n['node_id'] for n in route['nodes'] if len(n['前置节点编号列表'])>1]}


def materialize(root):
    _,_,route,mapping=current(root)
    data=read(root/'episode-synopses.json')
    if data.get('topology_hash') != load(root)['revisions'][-1]['hash']:
        raise ValueError('梗概未绑定当前冻结拓扑')
    items=data.get('nodes')
    if not isinstance(items,list) or len(items)!=len(route['nodes']) or {n.get('node_id') for n in items}!={n['node_id'] for n in route['nodes']}:
        raise ValueError('梗概须恰好覆盖每个正式节点')
    byid={n['node_id']:n for n in items}
    for n in route['nodes']:
        item=byid[n['node_id']]
        legacy._keys(item,{'node_id','单集梗概','本集冲突','stop_boundary'},'梗概投影')
        for key in ('单集梗概','本集冲突','stop_boundary'):
            n['route_material'][key]=item[key]
    errors=legacy.validate_route(route,require_accepted=False)
    if errors: raise ValueError('；'.join(errors))
    return route


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['freeze','status','ledger','materialize'])
    parser.add_argument('cache_root',type=Path)
    parser.add_argument('submission',nargs='?',type=Path)
    args=parser.parse_args(); root=args.cache_root
    try:
        if args.command=='freeze': result=freeze(root,read(args.submission))
        elif args.command=='status':
            state,plan,route,mapping=current(root)
            result={'topology_hash':state['revisions'][-1]['hash'],'revision':len(state['revisions']),
                    'node_id_map':mapping,'nodes':route['nodes']}
        elif args.command=='ledger':
            result=ledger(root); write(root/'route-ledger.json',result)
        else:
            result=materialize(root); write(root/'route-candidate.json',result)
        print(legacy.json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,RecursionError) as e:
        print(f'TOPOLOGY_REJECTED: {e}'); return 1
if __name__=='__main__': raise SystemExit(main())
