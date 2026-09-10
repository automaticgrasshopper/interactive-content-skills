"""Behavioral tests of graph checks, exact projection and scoped recovery."""
import sys, tempfile, unittest
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'business-skill-track/episode-skill-split/versions/0.19/episode-route-planner-biz/scripts'))
import graph_check as g
import route_plan as r
import route_contract as h


def scene(i,nxt,kind='scene',ending=None):
 return dict(id=i,kind=kind,source=i,next=nxt,ending_type=ending)
def choice(i,targets):
 return dict(id=i,kind='choice',question='现在如何行动？',options=[dict(text='采取动作'+str(k),target=t) for k,t in enumerate(targets)])
def part(i):
 return dict(id=i,title='事件'+i,text='人物在'+i+'经历当前事件并承受后果。',conflict='必须解决眼前阻力',stop_boundary='当前后果已经发生，下一动作尚未开始')
def story(parts):return dict(complete_story=''.join(p['text'] for p in parts),episodes=parts)
def fixture():
 nodes=[scene('a',['c1']),choice('c1',['l','r']),scene('l',['c2']),scene('r',['f']),choice('c2',['e','small']),scene('e',['j']),scene('f',['j']),scene('small',[],'ending','small'),scene('j',['c3']),choice('c3',['expected','k']),scene('expected',[],'ending','expected'),scene('k',['c4']),choice('c4',['true','bad']),scene('true',[],'ending','main'),scene('bad',[],'ending','failure')]
 return dict(nodes=nodes,mainline_path=['a','c1','l','c2','e','j','c3','k','c4','true'])

class GraphTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  (self.root/'user-request.md').write_text('我要一个40分钟的互动影视游戏。')
  r.write(self.root/'brief.json',dict(project_id='test',title='测试',summary='测试',duration_minutes=40))
  self.plan=fixture(); ids=['a','l','e','j','k','true']
  r.write(self.root/'mainline.json',story([part(i) for i in ids]));r.freeze(self.root)
  (self.root/'exploration.md').write_text('废弃草图，仅作探索。')
  self.branches=dict(stories=[story([part(n['id'])]) for n in self.plan['nodes'] if n['kind']!='choice' and n['id'] not in ids])
 def sub(self,old=None,affected=()):return dict(expected_hash=old['hash'] if old else None,reason='修复具体支线问题',affected_nodes=list(affected),plan=self.plan,branches=self.branches)
 def policy(self):return r.frozen(self.root)['policy']
 def test_complex_graph_has_witnesses(self):
  a=g.inspect(self.plan,self.policy());self.assertEqual(a['status'],'PASS');self.assertGreaterEqual(a['checks']['depth']['evidence']['depth'],2);self.assertTrue(a['checks']['crossing']['evidence']);self.assertTrue(a['checks']['progressive_ending']['evidence'])
 def test_episode_counts_exclude_choices(self):
  a=g.inspect(self.plan,self.policy());self.assertEqual(a['counts'],dict(episode_count=11,choice_node_count=4,ending_count=4,total_node_count=15))
 def test_paths_count_matches_enumeration(self):
  self.assertEqual(g.inspect(self.plan,self.policy())['path_count'],len(list(g.paths(self.plan))))
 def test_missing_small_fails(self):
  next(n for n in self.plan['nodes'] if n['id']=='small')['ending_type']='failure';self.assertIn('small',g.inspect(self.plan,self.policy())['failures'])
 def test_missing_fourth_type_fails_even_short(self):
  p=self.policy();p['long_story']=False;next(n for n in self.plan['nodes'] if n['id']=='true')['ending_type']='expected';self.assertIn('ending_types',g.inspect(self.plan,p)['failures'])
 def test_crossing_needs_independent_plot_nodes(self):
  p=dict(nodes=[scene('a',['c']),choice('c',['b','m']),scene('b',['m']),scene('m',['z']),scene('z',[],'ending','main')])
  self.assertEqual(g.inspect(p,self.policy())['checks']['crossing']['status'],'FAIL')
 def test_sequential_diamonds_are_not_nested(self):
  p=dict(nodes=[scene('a',['c1']),choice('c1',['b','c']),scene('b',['d']),scene('c',['d']),scene('d',['c2']),choice('c2',['e','f']),scene('e',['z']),scene('f',['z']),scene('z',[],'ending','main')])
  self.assertEqual(g.inspect(p,self.policy())['checks']['depth']['status'],'FAIL')
 def test_disconnected_graph_rejected(self):
  self.plan['nodes'].append(scene('isolated',[],'ending','small'))
  with self.assertRaises(ValueError):g.structure(self.plan)
 def test_cycle_rejected(self):
  next(n for n in self.plan['nodes'] if n['id']=='e')['next']=['l']
  with self.assertRaises(ValueError):g.structure(self.plan)
 def test_ending_cannot_continue(self):
  next(n for n in self.plan['nodes'] if n['id']=='small')['next']=['j']
  with self.assertRaises(ValueError):g.structure(self.plan)
 def test_empty_merge_rejected(self):
  self.plan['nodes'][1]['options'][1]['target']='l'
  with self.assertRaises(ValueError):g.structure(self.plan)
 def test_last_question_menu_rejected(self):
  p=dict(nodes=[scene('a',['c']),choice('c',['s','x','w','t'])]+[scene(i,[],'ending',k) for i,k in [('s','small'),('x','expected'),('w','failure'),('t','main')]])
  self.assertIn('ending_distribution',g.inspect(p,self.policy())['failures'])
 def test_source_projection_exact(self):
  state=r.submit(self.root,self.sub());route,mapping=r.materialize(self.root,state)
  for n in route['nodes']:
   if n['node_id']==mapping['a']:self.assertEqual(n['route_material']['单集梗概'],part('a')['text'])
  r.accept(self.root);r.verify(self.root)
 def test_rewrite_source_not_allowed(self):
  self.branches['stories'][0]['episodes'][0]['text']='另外编出的摘要'
  with self.assertRaisesRegex(ValueError,'PROJECTION'):r.submit(self.root,self.sub())
 def test_mainline_text_locked(self):
  (self.root/'mainline.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'MAINLINE_LOCK'):r.frozen(self.root)
 def test_mainline_graph_locked_on_repair(self):
  old=r.submit(self.root,self.sub());self.plan['nodes'][1]['question']='换了主线抉择'
  with self.assertRaisesRegex(ValueError,'MAINLINE_LOCK'):r.submit(self.root,self.sub(old,['c1']))
 def test_local_branch_repair_preserves_mainline(self):
  old=r.submit(self.root,self.sub());before=(self.root/'mainline.json').read_bytes()
  b=self.branches['stories'][0];b['episodes'][0]['text']+='人物承担新的实际代价。';b['complete_story']=b['episodes'][0]['text']
  new=r.submit(self.root,self.sub(old,[b['episodes'][0]['id']]));self.assertEqual(new['revision'],2);self.assertEqual(before,(self.root/'mainline.json').read_bytes());self.assertTrue((self.root/'history/revision-001.json').exists())
 def test_failed_crossing_repairs_without_rewriting_mainline(self):
  f=next(n for n in self.plan['nodes'] if n['id']=='f');f['next']=['small']
  old=r.submit(self.root,self.sub());self.assertIn('crossing',old['graph_report']['failures'])
  before=(self.root/'mainline.json').read_bytes();f['next']=['j']
  new=r.submit(self.root,self.sub(old,['f']));self.assertEqual(new['graph_report']['status'],'PASS')
  self.assertEqual((self.root/'mainline.json').read_bytes(),before)
  r.accept(self.root);r.verify(self.root)
 def test_stale_revision_rejected(self):
  r.submit(self.root,self.sub())
  with self.assertRaisesRegex(ValueError,'STALE'):r.submit(self.root,self.sub())
 def test_scope_enforced(self):
  old=r.submit(self.root,self.sub());b=self.branches['stories'][0];b['episodes'][0]['text']+='改变。';b['complete_story']=b['episodes'][0]['text']
  with self.assertRaisesRegex(ValueError,'REPAIR_SCOPE'):r.submit(self.root,self.sub(old))
 def test_passed_check_cannot_regress(self):
  old=r.submit(self.root,self.sub());next(n for n in self.plan['nodes'] if n['id']=='small')['ending_type']='failure'
  with self.assertRaisesRegex(ValueError,'REPAIR_REGRESSION'):r.submit(self.root,self.sub(old,['small']))
 def test_receipt_rejects_tampered_candidate(self):
  r.submit(self.root,self.sub());r.accept(self.root);p=r.read(self.root/'route-candidate.json');p['nodes'][0]['route_material']['单集梗概']='换故事';r.write(self.root/'route-candidate.json',p)
  with self.assertRaisesRegex(ValueError,'RECEIPT'):r.verify(self.root)
 def test_user_three_endings_not_forced_to_four(self):
  (self.root/'user-request.md').write_text('我要40分钟、3个结局的互动影视游戏。');p=r.policy(self.root);self.assertEqual(p['required_endings'],[]);self.assertEqual(p['hard_counts']['ending_count'],3)
 def test_duration_threshold(self):
  (self.root/'user-request.md').write_text('互动故事');b=r.read(self.root/'brief.json')
  for duration,expected in [(14.9,False),(15,True)]:
   b['duration_minutes']=duration;r.write(self.root/'brief.json',b);self.assertEqual(r.policy(self.root)['long_story'],expected)
 def test_fabricated_exemption_rejected(self):
  b=r.read(self.root/'brief.json');b['user_overrides']={'exemptions':[{'rule':'depth','quote':'不要复杂','reason':'难写'}]};r.write(self.root/'brief.json',b)
  with self.assertRaisesRegex(ValueError,'USER_CONSTRAINT'):r.policy(self.root)
 def test_formal_handoff_still_valid(self):
  r.submit(self.root,self.sub());r.accept(self.root,self.root/'formal.json');self.assertEqual(h.validate(r.read(self.root/'formal.json'),require_accepted=True),[])

if __name__=='__main__':unittest.main()
