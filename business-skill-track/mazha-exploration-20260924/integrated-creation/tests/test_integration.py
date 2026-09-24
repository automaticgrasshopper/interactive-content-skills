import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'skills/mazha-route-0924/scripts'
sys.path.insert(0, str(SCRIPTS))
import graph_audit as ga
import graph_check as gc
import screenplay_contract as sc
import stage_contract as st
from build_enhancer_input import build
from validate_compact_draft import validate


def scene(i, targets, kind='scene', ending=None):
    return dict(id=i,kind=kind,source=i,next=targets,ending_type=ending)
def choice(i, targets):
    return dict(id=i,kind='choice',question='怎么行动？',options=[dict(text='调查'+str(k),target=t) for k,t in enumerate(targets)])
def policy(**extra):
    return dict(scope='full',frontiers=[],long_story=True,hard_counts={},required_endings=['small','expected','failure','main'],forbidden_endings=[],ending_override=False,exemptions={},**extra)
def loop_plan():
    return {'nodes':[scene('intro',['hub']),scene('hub',['c']),choice('c',['clue','out']),scene('clue',['hub']),scene('out',[],'ending','main')],
            'loops':[{'hub':'hub','choice':'c','returns':[{'source':'clue','target':'hub'}], 'exits':[{'source':'c','target':'out'}], 'state_mode':'repeat_safe','repeat_contract':'入口在环外；枢纽只说仍可查看房间，出口始终可选。'}]}

class GraphChecks(unittest.TestCase):
    def test_original_rich_and_degenerate_graphs_still_have_same_reports(self):
        # Execute only pre-existing fixture function definitions, no old tests
        # or their sys.path mutations. Compare new adapter against proven core.
        repo = ROOT.parents[2]
        tree=ast.parse((repo/'tests/test_route_planner_020.py').read_text())
        funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
        ns={};exec(compile(ast.Module(body=funcs,type_ignores=[]),'<original-fixtures>','exec'),ns)
        for fixture in ('fixture','woven_fixture','rich_fixture'):
            plan=ns[fixture]()
            old=gc.inspect(plan,policy());new=ga.audit(plan,policy())
            for field in ('status','checks','counts','failures','path_count'):
                self.assertEqual(old[field],new[field])
        self.assertEqual(ga.audit(ns['rich_fixture'](),policy())['status'],'PASS')
        self.assertIn('woven',ga.audit(ns['fixture'](),policy())['failures'])
    def test_loop_not_allowed_in_free_topology(self):
        with self.assertRaisesRegex(ValueError,'explicit request'):ga.audit(loop_plan(),policy())
    def test_explicit_loop_is_review_not_fake_full_pass(self):
        p=policy(loop_authorization='explicit_user_request');p['required_endings']=['main']
        report=ga.audit(loop_plan(),p)
        self.assertEqual(report['status'],'REVIEW_REQUIRED')
        self.assertIsNone(report['path_count'])
        self.assertEqual(report['runtime_loop_support'],'UNVERIFIED')
    def test_existing_loop_maintenance(self):
        p=policy(loop_authorization='existing_canvas');p.update(scope='batch')
        self.assertEqual(ga.audit(loop_plan(),p)['status'],'REVIEW_REQUIRED')
    def test_closed_cycle_rejected(self):
        p=loop_plan();p['nodes'][-1]=scene('out',['hub'])
        with self.assertRaisesRegex(ValueError,'cannot reach'):ga.audit(p,policy(loop_authorization='explicit_user_request'))
    def test_fake_exit_inside_cycle_rejected(self):
        p=loop_plan();p['loops'][0]['exits']=[{'source':'c','target':'clue'}]
        with self.assertRaisesRegex(ValueError,'actually leave'):ga.audit(p,policy(loop_authorization='explicit_user_request'))
    def test_unlisted_cycle_rejected(self):
        p=loop_plan();p['loops']=[]
        with self.assertRaisesRegex(ValueError,'Undeclared'):ga.audit(p,policy(loop_authorization='explicit_user_request'))
    def test_wrong_return_target_rejected(self):
        p=loop_plan();p['loops'][0]['returns'][0]['target']='intro'
        with self.assertRaisesRegex(ValueError,'declared hub'):ga.audit(p,policy(loop_authorization='explicit_user_request'))
    def test_frontier_not_fake_ending(self):
        plan={'nodes':[scene('a',['c']),choice('c',['b','d']),scene('b',[]),scene('d',[])]}
        p=policy();p.update(scope='batch',frontiers=['b','d'])
        report=ga.audit(plan,p)
        self.assertEqual(report['status'],'BATCH_STRUCTURE_PASS');self.assertEqual(report['counts']['ending_count'],0)
        p['scope']='full'
        with self.assertRaisesRegex(ValueError,'full work'):ga.audit(plan,p)
    def test_no_silent_unfinished_node(self):
        with self.assertRaisesRegex(ValueError,'frontier'):ga.audit({'nodes':[scene('a',[])]},policy())
    def test_choice_cannot_skip_consequence(self):
        p={'nodes':[scene('a',['c']),choice('c',['d','z']),choice('d',['x','y']),scene('x',[],'ending','small'),scene('y',[],'ending','failure'),scene('z',[],'ending','main')]}
        with self.assertRaisesRegex(ValueError,'consequence'):ga.audit(p,policy())
    def test_dangling_edge(self):
        with self.assertRaisesRegex(ValueError,'Dangling'):ga.audit({'nodes':[scene('a',['missing'])]},policy())

class WriterChecks(unittest.TestCase):
    def setUp(self):
        self.text='【便利店·雨夜·内】\n林雨把湿钥匙放到柜台上。\n林雨（迟疑）：“这是哥哥的钥匙。”\n门外传来刹车声，林雨攥紧钥匙。'
    def test_missing_choice_projection_is_rejected(self):
        self.assertTrue(sc.interaction_issues({'互动节点':{'question':'怎么选','options':[]}}))
        value={'是否为分支节点':True,'是否有选择问题':True,'选择问题':'去哪','选项列表':[{'选项编号':'a','选项文字':'查柜台','目标分集编号':'n2'},{'选项编号':'b','选项文字':'找哥哥','目标分集编号':'n3'}],'默认下一分集编号':'无'}
        self.assertEqual(sc.interaction_issues({'互动节点':value}),[])
        value['选项列表']=[]
        self.assertTrue(sc.interaction_issues({'互动节点':value}))
    def test_fixed_format_accepts_real_newlines(self):self.assertEqual(sc.format_issues(self.text),[])
    def test_bad_formats(self):
        for text in (self.text.replace('\n','\n\n'),self.text.replace('林雨（迟疑）：','林雨：'),self.text.replace('·雨夜·','·雨夜·暴雨·'),self.text.replace('\n',r'\n'),self.text+'\n# 分析'):
            self.assertTrue(sc.format_issues(text),text)
    def test_packet_draft_reference_tampering_cannot_reuse_receipt(self):
        packet='WRITING_PACKET_VERSION='+st.PACKET_VERSION+'\n{}\n'
        draft='【便利店·雨夜·内】\n林雨拿到钥匙，听见哥哥的车停在门口。'
        self.assertEqual(validate(packet,draft),[])
        receipt={'contract_version':st.RECEIPT_VERSION,'status':'PASS','writing_packet_sha256':st.digest(packet),'compact_draft_sha256':st.digest(draft)}
        self.assertIn(draft,build(packet,draft,receipt,'增强规则','对白规则'))
        for changed_packet,changed_draft in ((packet+'改动',draft),(packet,draft+'逃走')):
            with self.assertRaises(ValueError):build(changed_packet,changed_draft,receipt,'增强规则','对白规则')
    def test_complete_staged_acceptance_and_stale_input_rejection(self):
        material={'单集梗概':'林雨捡到钥匙，哥哥的车停在门口。','本集冲突':'要不要告诉哥哥','entry_state':{},'state_changes':{},'allowed_characters':['林雨'],'allowed_scenes':['便利店'],'allowed_props':['钥匙'],'stop_boundary':'听见车声，尚未出门'}
        node={'node_id':'real-node-1','route_material':material,'前置节点编号列表':[],'后续节点编号列表':[],'互动节点':{'是否为分支节点':False,'是否有选择问题':False,'选择问题':'','选项列表':[],'默认下一分集编号':'无'}}
        node['node_route_material_hash']=sc.node_hash(node)
        route={'contract_version':sc.ROUTE_VERSION,'capability_id':sc.ROUTE_CAPABILITY_ID,'project_id':'test-project','route_id':'test-route','route_version':'current','route_status':'accepted','nodes':[node]}
        route['route_output_hash']=sc.route_hash(route)
        context={'contract_version':st.CONTEXT_VERSION,**{k:route[k] for k in ('project_id','route_id','route_version','route_output_hash')},'node_id':node['node_id'],'node_route_material_hash':node['node_route_material_hash'],'characters':[dict(name='林雨',public_identity='店员',identity_anchor='店员',current_relevance='发现钥匙的人')],'scenes':[dict(name='便利店',public_description='临街的店')],'props':[dict(name='钥匙',public_description='柜台上的湿钥匙')],'direct_predecessor_endings':[]}
        packet=st.build_packet(route,context,node['node_id'])
        evidence='林雨把湿钥匙放到柜台上。'
        checks=[dict(check=k,passed=True,evidence=[evidence]) for k in sc.REQUIRED_CHECKS|{'dialogue'}]
        screenplay={'分集剧本':{'完整剧本':self.text},'剧本创作分析':{k:'钥匙出现使林雨面临哥哥即将进门的压力。' for k in sc.ANALYSIS_FIELDS},'关联角色':['林雨'],'关联场景':['便利店'],'关联道具':['钥匙'],'派生信息':{},'quality_checks':checks}
        screenplay['剧本创作分析']['验收结论']='PASS'
        patch={'contract_version':sc.CONTRACT_VERSION,'capability_id':sc.CAPABILITY_ID,**{k:route[k] for k in ('project_id','route_id','route_version','route_output_hash')},'node_id':node['node_id'],'node_route_material_hash':node['node_route_material_hash'],'screenplay':screenplay,'screenplay_hash':None,'status':'draft','accepted_at':None}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name,data in [('route',route),('context',context),('draft',patch)]:
                (p/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False))
            (p/'packet.txt').write_text(packet)
            (p/'compact.md').write_text('【便利店·雨夜·内】\n林雨捡到哥哥的钥匙，哥哥的车停在门口。')
            (p/'enhanced.md').write_text(self.text)
            def run(name,*args):return subprocess.run([sys.executable,str(SCRIPTS/name),*[str(p/a) for a in args]],capture_output=True,text=True)
            self.assertEqual(run('validate_compact_draft.py','packet.txt','compact.md','receipt.json').returncode,0)
            self.assertEqual(run('build_enhancer_input.py','packet.txt','compact.md','receipt.json','enhancer.txt').returncode,0)
            args=['route.json','context.json','packet.txt','compact.md','receipt.json','enhancer.txt','enhanced.md','draft.json','out.json']
            result=run('accept_node_screenplay.py',*args)
            self.assertEqual(result.returncode,0,result.stdout)
            accepted=(p/'out.json').read_bytes()
            (p/'compact.md').write_text('换成其他剧情')
            result=run('accept_node_screenplay.py',*args)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual((p/'out.json').read_bytes(),accepted)

if __name__=='__main__':unittest.main()
