"""Behavioral contract tests; fixture PASS labels are not model quality evidence."""
import sys, json, tempfile, unittest
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'business-skill-track/episode-skill-split/versions/0.19/episode-route-planner-biz/scripts'))
import topology_plan as t, planned_gate as pg, planning_gate as gate, user_constraints as uc, workflow_state as wf

class PlannedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Path(self.tmp.name)
  self.text='人物停在两条路前。人物取得录音。人物携带证据进入共同任务。人物完成交证结算。'
  parts=['人物停在两条路前。','人物取得录音。','人物携带证据进入共同任务。','人物完成交证结算。']
  values={'user-request.md':'互动影视游戏','user-intent-lock.json':{'hard_counts':uc.parse_explicit_counts('互动影视游戏'),'shape_mode':'open'},
  'creative-brief.json':{'project_id':'test-019','title':'两路交证','characters':[],'scenes':[],'props':[],'initial_state':{}},
  'complete-story.json':{'contract_version':'nextplay.episode-complete-story.v1','title':'两路交证','complete_story':self.text},
  'mainline-decomposition.json':{'mainline_segments':[{'segment_id':f's{i}','source_text':p} for i,p in enumerate(parts)]},
  'mainline-emotional-movement.json':{'emotional_movements':[dict(movement_id='m1',segment_ids=[f's{i}' for i in range(4)],pressure='证据将消失',desired_state='取得证据',reality_shift='两路只能选一',control_change='必须决定',unresolved_task='证明真相',candidate_fissures=[])]},
  'decision-fissure-audit.json':{'decision_fissures':[]},'story-treatment.json':{'choices':[],'endings':[]}}
  for name,v in values.items():
   if isinstance(v,str):(self.r/name).write_text(v)
   else:self.put(name,v)
  self.plan={'nodes':[self.node('a','choice','s0'),self.node('b','scene','s1'),self.node('c'),self.node('d','scene','s2'),self.node('e','ending','s3')],
             'edges':[self.edge('a','b',0),self.edge('a','c',1),self.edge('b','d'),self.edge('c','d'),self.edge('d','e')]}
  self.plan['nodes'][1]['route_material']['state_changes']={'proof':'recording','debt':'A'}
  self.plan['nodes'][2]['route_material']['state_changes']={'proof':'witness','debt':'B'}
  self.plan['nodes'][3]['route_material']['entry_state']={'proof':{'one_of':['recording','witness']}}
 def put(self,name,v): (self.r/name).write_text(json.dumps(v,ensure_ascii=False))
 def edge(self,a,b,i=None):return dict(source_node_id=a,target_node_id=b,option_index=i)
 def node(self,id,kind='scene',seg=None):
  n=dict(node_id=id,kind=kind,title='人物取得具体证据',ending_type='main' if kind=='ending' else None,emotional_movement_ids=['m1'],mainline_segment_id=seg,
    route_material={'单集梗概':'人物在现场面对明确阻力，确认眼前事件和已知事实，采取当前行动后承受直接后果。','本集冲突':'人物必须在明确阻力下取得眼前证据。','entry_state':{},'state_changes':{},'allowed_characters':[],'allowed_scenes':[],'allowed_props':[],'stop_boundary':'人物确认当前事实并停在新的行动开始之前。'})
  if kind=='choice':n.update(question='人物此刻从哪里取得证据？',options=['前往寻找录音','前往寻找目击者'])
  return n
 def freeze(self,hash=None):return t.freeze(self.r,{'expected_topology_hash':hash,'reason':'创建或修正当前节点事实','plan':self.plan})
 def complete(self):
  self.freeze();self.put('route-ledger.json',t.ledger(self.r));p=pg.packet(self.r)
  for which in ('A','B'):
   self.put(f'topology-review-{which}.json',{'packet_hash':p['packet_hash'],'review_pass':which,'verdict':'PASS','issues':[],
     'checks':[{'check':c,'passed':True,'explanation':'测试夹具，只验证回执协议','evidence':[{'node_id':'episode-001','quote':'人物在现场面对明确阻力'}]} for c in pg.CHECKS]})
  route=t.current(self.r)[2]
  self.put('episode-synopses.json',{'topology_hash':t.load(self.r)['revisions'][-1]['hash'],'nodes':[{'node_id':n['node_id'],**{k:n['route_material'][k] for k in ('单集梗概','本集冲突','stop_boundary')}} for n in route['nodes']]})
  route=t.materialize(self.r);self.put('route-candidate.json',route)
  self.put('synopsis-review.json',{'candidate_hash':t.digest(route),'verdict':'PASS','issues':[], 'nodes':[{'node_id':n['node_id'],'consistent':True,'choice_pending':True,'quote':'人物在现场面对明确阻力','explanation':'测试夹具'} for n in route['nodes']]})
  self.put('emotional-spine.json',{'emotional_spine':[{'node_id':n['node_id'],'valence':0,'arousal':0,'dominance':0,'turn':False,'turn_reason':''} for n in route['nodes']]})
  self.put('planning-acceptance.json',gate.build_from_root(self.r))
 def test_01_natural_counts(self):
  c=uc.parse_explicit_counts('我要12个剧情节点、3个结局。');self.assertEqual(c['episode_count'],12);self.assertEqual(c['ending_count'],3)
 def test_02_merge_retains_each_branch_state(self):
  self.freeze();p=t.ledger(self.r);self.assertEqual(p['path_count'],2);self.assertEqual({x['exit_state']['debt'] for x in p['paths']},{'A','B'})
 def test_03_merge_rejects_other_branch_exclusive_fact(self):
  self.plan['nodes'][3]['route_material']['entry_state']={'proof':'recording'};self.freeze()
  with self.assertRaisesRegex(ValueError,'前提不满足'):t.ledger(self.r)
 def test_04_future_target_not_limited_by_creation_order(self):
  self.plan['nodes'][2],self.plan['nodes'][3]=self.plan['nodes'][3],self.plan['nodes'][2]
  self.freeze();self.assertEqual(t.ledger(self.r)['path_count'],2)
 def test_05_no_four_ending_minimum(self):
  req='4个剧情节点、1个结局';(self.r/'user-request.md').write_text(req);self.put('user-intent-lock.json',{'hard_counts':uc.parse_explicit_counts(req),'shape_mode':'open'});self.freeze()
 def test_06_fixed_count_mismatch_never_freezes(self):
  req='12个剧情节点、3个结局';(self.r/'user-request.md').write_text(req);self.put('user-intent-lock.json',{'hard_counts':uc.parse_explicit_counts(req),'shape_mode':'open'})
  with self.assertRaisesRegex(ValueError,'硬数量'):self.freeze()
  self.assertFalse((self.r/'topology-state.json').exists())
 def test_07_exploration_cannot_invalidate_receipt(self):
  self.complete();(self.r/'topology-exploration.md').write_text('任意不完整草图');self.assertEqual(gate.verify_root(self.r),[])
 def test_08_spine_no_backwrite_or_ab_invalidation(self):
  self.complete();before=(self.r/'topology-state.json').read_bytes();p=pg.packet(self.r)['packet_hash'];d=t.read(self.r/'emotional-spine.json');d['emotional_spine'][0]['valence']=0.5;self.put('emotional-spine.json',d)
  self.assertEqual(before,(self.r/'topology-state.json').read_bytes());self.assertEqual(p,pg.packet(self.r)['packet_hash']);pg.review(self.r,'A');self.assertTrue(gate.verify_root(self.r));self.put('planning-acceptance.json',gate.build_from_root(self.r));self.assertEqual(gate.verify_root(self.r),[])
 def test_09_choice_already_executed_review_rejected(self):
  self.complete();d=t.read(self.r/'synopsis-review.json');d['nodes'][0]['choice_pending']=False;self.put('synopsis-review.json',d);self.assertTrue(gate.verify_root(self.r))
 def test_10_synopsis_cannot_add_edge_or_state(self):
  self.complete();d=t.read(self.r/'episode-synopses.json');d['nodes'][0]['edges']=[];self.put('episode-synopses.json',d)
  with self.assertRaisesRegex(ValueError,'字段错误'):t.materialize(self.r)
 def test_11_a_does_not_require_b(self):
  self.complete();(self.r/'topology-review-B.json').unlink();pg.review(self.r,'A');self.assertEqual(wf.status(self.r)['next_actions'][0]['action'],'REVIEW_TOPOLOGY_B')
 def test_12_local_revision_preserves_others_and_invalidates(self):
  self.complete();before=t.load(self.r);self.plan['nodes'][2]['title']='修正此节点的具体事实';self.freeze(before['revisions'][-1]['hash']);after=t.load(self.r)
  self.assertEqual(before['revisions'],after['revisions'][:-1]);self.assertEqual(before['revisions'][-1]['plan']['nodes'][0],after['revisions'][-1]['plan']['nodes'][0]);self.assertFalse((self.r/'planning-acceptance.json').exists());self.assertTrue((self.r/'repair-history/2/planning-acceptance.json').exists());self.assertEqual(wf.status(self.r)['next_actions'][0]['action'],'DERIVE_ROUTE_LEDGER')
 def test_13_stale_revision_rejected_without_mutation(self):
  self.freeze();before=(self.r/'topology-state.json').read_bytes()
  with self.assertRaisesRegex(ValueError,'陈旧'):self.freeze()
  self.assertEqual(before,(self.r/'topology-state.json').read_bytes())
 def test_14_cycle_rejected(self):
  self.plan['edges'].append(self.edge('e','a'))
  with self.assertRaises(ValueError):self.freeze()
 def test_15_candidate_tamper_rejected(self):
  self.complete();d=t.read(self.r/'route-candidate.json');d['nodes'][1]['route_material']['state_changes']={};self.put('route-candidate.json',d);self.assertTrue(gate.verify_root(self.r))
 def test_17_title_only_review_evidence_rejected(self):
  self.complete();d=t.read(self.r/'topology-review-B.json');d['checks'][0]['evidence']=[{'node_id':'episode-001','quote':'人物取得具体证据'}];self.put('topology-review-B.json',d)
  with self.assertRaisesRegex(ValueError,'不能用标题'):pg.review(self.r,'B')
 def test_16_end_to_end_handoff_still_accepted(self):
  self.complete();self.assertEqual(gate.verify_root(self.r),[])
  from route_contract import seal,validate
  accepted=seal(t.read(self.r/'route-candidate.json'));self.assertEqual(validate(accepted,require_accepted=True),[])
if __name__=='__main__':unittest.main()
