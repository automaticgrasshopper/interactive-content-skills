#!/usr/bin/env python3
"""One-way evidence gates for planned topology; semantic verdicts need real reading."""
from pathlib import Path
import argparse
import json
import topology_plan as topology
from route_growth import digest, _read as read

CHECKS = ('主线投影与决定裂缝','选项尚未执行且后果互异','分支持续差异与回汇承接',
          '结局解锁与因果结算','戏剧单位与结构复杂度','用户题材与硬约束')
FILES = (*topology.UPSTREAM_FILES,'topology-state.json','route-ledger.json',
         'topology-review-A.json','topology-review-B.json','episode-synopses.json',
         'route-candidate.json','synopsis-review.json','emotional-spine.json')

def packet(root):
    state,plan,route,mapping=topology.current(root)
    expected=topology.ledger(root)
    if read(root/'route-ledger.json') != expected:
        raise ValueError('路线记账未绑定当前拓扑或路径不完整')
    material={'upstream_hashes':state['upstream_hashes'],'topology_hash':state['revisions'][-1]['hash'],
              'nodes':route['nodes'],'edges':route['edges'],'ledger':expected,
              'upstream':{name:(root/name).read_text(encoding='utf-8') for name in topology.UPSTREAM_FILES}}
    return {'packet_hash':digest(material),'material':material,'required_checks':list(CHECKS)}

def review(root,which):
    p=packet(root); data=read(root/f'topology-review-{which}.json')
    if data.get('packet_hash')!=p['packet_hash'] or data.get('review_pass')!=which or data.get('verdict')!='PASS' or data.get('issues')!=[]:
        raise ValueError(f'拓扑{which}复检未通过或依据已过期')
    checks=data.get('checks',[])
    if len(checks)!=len(CHECKS) or {c.get('check') for c in checks}!=set(CHECKS):
        raise ValueError(f'拓扑{which}复检覆盖不完整')
    byid={n['node_id']:n for n in p['material']['nodes']}
    for c in checks:
        if c.get('passed') is not True or not c.get('explanation') or not c.get('evidence'):
            raise ValueError('复检需要判断、理由与逐字节点证据')
        for ev in c['evidence']:
            n=byid.get(ev.get('node_id'))
            quote=ev.get('quote')
            text=json.dumps(n,ensure_ascii=False) if n else ''
            if not isinstance(quote,str) or not quote.strip() or quote not in text:
                raise ValueError('复检逐字证据不属于当前节点')
    return data

def synopsis_review(root,candidate):
    data=read(root/'synopsis-review.json')
    if data.get('candidate_hash')!=digest(candidate) or data.get('verdict')!='PASS' or data.get('issues')!=[]:
        raise ValueError('梗概复检未通过或已过期')
    checks=data.get('nodes',[])
    if len(checks)!=len(candidate['nodes']) or {c.get('node_id') for c in checks}!={n['node_id'] for n in candidate['nodes']}:
        raise ValueError('梗概复检未逐节点覆盖')
    byid={n['node_id']:n for n in candidate['nodes']}
    for c in checks:
        n=byid[c['node_id']]
        if c.get('consistent') is not True or not c.get('explanation'):
            raise ValueError('梗概事件归属尚未通过')
        q=c.get('quote')
        if not isinstance(q,str) or not q.strip() or q not in n['route_material']['单集梗概']:
            raise ValueError('梗概复检需要当前正文逐字证据')
        if n['互动节点']['是否为分支节点'] and c.get('choice_pending') is not True:
            raise ValueError('选择节点须确认选项尚未执行')

def validate(root):
    import planning_gate as gate
    initial={n:gate.file_sha256(root/n) for n in FILES}
    errors=[]; gate.validate_upstream(root,errors)
    if errors: raise ValueError('；'.join(errors))
    packet(root); review(root,'A'); review(root,'B')
    candidate=topology.materialize(root)
    if read(root/'route-candidate.json')!=candidate:
        raise ValueError('正式候选不是冻结拓扑与梗概的确定性投影')
    synopsis_review(root,candidate)
    # Reuse the precise numeric spine checks without creating or mutating artifacts.
    spine=read(root/'emotional-spine.json').get('emotional_spine')
    if not isinstance(spine,list) or [n.get('node_id') for n in spine]!=[n['node_id'] for n in candidate['nodes']]:
        raise ValueError('情绪脊未按顺序覆盖全部节点')
    import math
    for n in spine:
        for key in ('valence','arousal','dominance'):
            v=n.get(key)
            if type(v) not in (int,float) or not math.isfinite(v) or not -1<=v<=1:
                raise ValueError('情绪脊数值非法')
        if type(n.get('turn')) is not bool or not isinstance(n.get('turn_reason'),str) or (n['turn'] and not n['turn_reason'].strip()):
            raise ValueError('情绪脊拐点说明非法')
    files={n:gate.file_sha256(root/n) for n in FILES}
    if files!=initial: raise ValueError('验收期间证据变化')
    return candidate,files

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['packet','A','B','synopsis-packet','synopsis'])
    p.add_argument('cache_root',type=Path); args=p.parse_args(); root=args.cache_root
    try:
        if args.command=='packet': result=packet(root)
        elif args.command in ('A','B'): result=review(root,args.command)
        elif args.command=='synopsis-packet':
            candidate=topology.materialize(root)
            result={'candidate_hash':digest(candidate),'nodes':candidate['nodes']}
        else:
            synopsis_review(root,topology.materialize(root)); result={'status':'PASS'}
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(f'REVIEW_REJECTED: {e}'); return 1
if __name__=='__main__': raise SystemExit(main())
