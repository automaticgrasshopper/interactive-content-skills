"""Behavioral tests of graph checks, exact projection and scoped recovery."""
import sys, tempfile, unittest
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'business-skill-track/episode-skill-split/versions/0.20/episode-route-planner-biz/scripts'))
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

def woven_fixture():
 p=fixture()
 next(n for n in p['nodes'] if n['id']=='r')['next']=['rc']
 next(n for n in p['nodes'] if n['id']=='c2')['options'].append(dict(text='走另一翼',target='f'))
 p['nodes'].append(choice('rc',['e','f']))
 return p

def rich_fixture():
 p=woven_fixture()
 for n in p['nodes']:
  if n['id'] in ('e','f'): n['next']=[n['id']+'c']
  if n['id']=='c4': n['options']=[dict(text='停在第二层兑现',target='expected2'),dict(text='继续承担代价',target='w')]
 p['nodes'] += [choice('ec',['u','v']),choice('fc',['u','v']),scene('u',['s']),scene('v',['s']),
  choice('s',['g','h']),scene('g',['gc']),scene('h',['hc']),choice('gc',['j','small']),choice('hc',['j','bad']),
  scene('expected2',[],'ending','expected'),scene('w',['c5']),choice('c5',['true','bad'])]
 p['mainline_path']=['a','c1','l','c2','e','ec','u','s','g','gc','j','c3','k','c4','w','c5','true']
 return p

class GraphTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  (self.root/'user-request.md').write_text('我要一个40分钟的互动影视游戏。')
  r.write(self.root/'brief.json',dict(project_id='test',title='测试',summary='测试',duration_minutes=40))
  self.plan=rich_fixture(); ids=['a','l','e','u','g','j','k','w','true']
  (self.root/'mainline-story.md').write_text(story([part(i) for i in ids])['complete_story'])
  r.write(self.root/'mainline.json',story([part(i) for i in ids]));r.freeze(self.root)
  (self.root/'exploration.md').write_text('废弃草图，仅作探索。')
  self.branches=dict(stories=[story([part(n['id'])]) for n in self.plan['nodes'] if n['kind']!='choice' and n['id'] not in ids])
 def sub(self,old=None,affected=()):return dict(expected_hash=old['hash'] if old else None,reason='修复具体支线问题',affected_nodes=list(affected),plan=self.plan,branches=self.branches)
 def policy(self):return r.frozen(self.root)['policy']
 def test_complex_graph_has_witnesses(self):
  a=g.inspect(self.plan,self.policy());self.assertEqual(a['status'],'PASS');self.assertGreaterEqual(a['checks']['depth']['evidence']['depth'],2);self.assertTrue(a['checks']['crossing']['evidence']);self.assertTrue(a['checks']['progressive_ending']['evidence'])
 def test_plain_diamond_with_later_depth_is_not_developed_merge(self):
  p=fixture();next(n for n in p['nodes'] if n['id']=='l')['next']=['e']
  p['nodes']=[n for n in p['nodes'] if n['id'] not in ('c2','small')]
  report=g.inspect(p,self.policy())
  self.assertEqual(report['checks']['depth']['status'],'PASS')
  self.assertEqual(report['checks']['crossing']['status'],'FAIL')
  self.assertTrue(report['checks']['branch_shapes']['evidence']['simple_merges'])
 def test_single_deep_is_not_called_woven(self):
  shapes=g.inspect(fixture(),self.policy())['checks']['branch_shapes']['evidence']
  self.assertTrue(shapes['single_deep']);self.assertFalse(shapes['double_wing']);self.assertFalse(shapes['woven'])
 def test_two_wings_with_one_merge_are_not_woven(self):
  p=fixture();next(n for n in p['nodes'] if n['id']=='r')['next']=['rc']
  p['nodes'] += [choice('rc',['f','rf']),scene('rf',[],'ending','failure')]
  shapes=g.inspect(p,self.policy())['checks']['branch_shapes']['evidence']
  self.assertTrue(shapes['double_wing']);self.assertFalse(shapes['woven'])
 def test_woven_requires_two_distinct_shared_stages(self):
  p=dict(nodes=[scene('a',['c']),choice('c',['l','r']),scene('l',['lc']),scene('r',['rc']),
   choice('lc',['la','lb']),choice('rc',['ra','rb']),scene('la',['x']),scene('ra',['x']),
   scene('lb',['y']),scene('rb',['y']),scene('x',['j']),scene('y',['j']),scene('j',['z']),scene('z',[],'ending','main')])
  shapes=g.inspect(p,self.policy())['checks']['branch_shapes']['evidence']
  self.assertTrue(shapes['woven']);self.assertEqual(set(shapes['woven'][0]['shared_stages']),{'x','y'})
 def test_explicit_crossing_override_still_wins(self):
  p=dict(nodes=[scene('a',['c']),choice('c',['b','d']),scene('b',['j']),scene('d',['j']),scene('j',['z']),scene('z',[],'ending','main')])
  policy=self.policy();policy['exemptions']['crossing']={'quote':'不要交叉'}
  self.assertEqual(g.inspect(p,policy)['checks']['crossing']['status'],'EXEMPT')
 def test_a_alone_fails_long_story(self):
  self.assertIn('woven',g.inspect(fixture(),self.policy())['failures'])
 def test_b_without_c_fails_long_story(self):
  p=fixture();next(n for n in p['nodes'] if n['id']=='r')['next']=['rc'];p['nodes'] += [choice('rc',['f','rf']),scene('rf',[],'ending','failure')]
  report=g.inspect(p,self.policy());self.assertTrue(report['checks']['branch_shapes']['evidence']['double_wing']);self.assertIn('woven',report['failures'])
 def test_woven_gate_exempts_only_explicit_user_override(self):
  policy=self.policy();policy['exemptions']['woven']={'quote':'我只要普通菱形','reason':'用户锁定简单结构'}
  self.assertEqual(g.inspect(fixture(),policy)['checks']['woven']['status'],'EXEMPT')
 def test_short_story_does_not_require_woven(self):
  policy=self.policy();policy['long_story']=False;self.assertNotIn('woven',g.inspect(fixture(),policy)['failures'])
 def test_no_choice_user_override_includes_woven(self):
  (self.root/'user-request.md').write_text('不要选择，40分钟，1个结局。')
  self.assertIn('woven',r.policy(self.root)['exemptions'])
 def test_episode_counts_exclude_choices(self):
  a=g.inspect(woven_fixture(),self.policy());self.assertEqual(a['counts'],dict(episode_count=11,choice_node_count=5,ending_count=4,total_node_count=16))
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
 def test_failed_ladder_repairs_without_rewriting_mainline(self):
  n=next(n for n in self.plan['nodes'] if n['id']=='expected2');n['ending_type']='failure'
  old=r.submit(self.root,self.sub());self.assertIn('ending_ladder',old['graph_report']['failures'])
  before=(self.root/'mainline.json').read_bytes();n['ending_type']='expected'
  new=r.submit(self.root,self.sub(old,['expected2']));self.assertEqual(new['graph_report']['status'],'PASS')
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

 def test_new_freeze_requires_independent_story_source(self):
  (self.root/'mainline-lock.json').unlink();(self.root/'mainline-story.md').unlink()
  self.assertEqual(r.status(self.root),{'next':'WRITE_INPUT','file':'mainline-story.md'})
  with self.assertRaises(FileNotFoundError):r.freeze(self.root)
  self.assertFalse((self.root/'mainline-lock.json').exists())
 def test_summarized_slices_cannot_replace_independent_story(self):
  (self.root/'mainline-lock.json').unlink()
  original=(self.root/'mainline-story.md').read_bytes()
  main=r.read(self.root/'mainline.json');main['episodes'][0]['text']='省略交谈和过程的摘要。';main['complete_story']=''.join(p['text'] for p in main['episodes']);r.write(self.root/'mainline.json',main)
  with self.assertRaisesRegex(ValueError,'PROJECTION'):r.freeze(self.root)
  self.assertEqual((self.root/'mainline-story.md').read_bytes(),original)
  self.assertFalse((self.root/'mainline-lock.json').exists())
 def test_independent_source_is_locked(self):
  self.assertIn('mainline-story.md',r.frozen(self.root)['files'])
  (self.root/'mainline-story.md').write_text('改写原文')
  with self.assertRaisesRegex(ValueError,'MAINLINE_LOCK'):r.frozen(self.root)
 def test_pre_source_cache_still_verifies_without_backfilling(self):
  lock=r.read(self.root/'mainline-lock.json');del lock['files']['mainline-story.md'];r.write(self.root/'mainline-lock.json',lock)
  (self.root/'mainline-story.md').unlink()
  r.submit(self.root,self.sub());r.accept(self.root);r.verify(self.root)
  self.assertFalse((self.root/'mainline-story.md').exists())

 def cli(self, action, *extra):
  import subprocess, json
  result=subprocess.run([sys.executable,r.__file__,action,str(self.root),*map(str,extra)],capture_output=True,text=True)
  return result
 def test_cli_pending_graph_and_accept_do_not_report_execution_error(self):
  next(n for n in self.plan['nodes'] if n['id']=='small')['ending_type']='failure'
  r.submit(self.root,self.sub())
  before=(self.root/'topology-state.json').read_bytes()
  import json
  for action in ('submit','check','accept'):
   extra=[]
   if action=='submit':
    submission=self.root/'submission.json';r.write(submission,self.sub(r.current(self.root)));extra=[submission]
   if action=='accept':extra=[self.root/'formal.json']
   result=self.cli(action,*extra)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   payload=json.loads(result.stdout);self.assertEqual(payload['status'],'NEEDS_REPAIR');self.assertFalse(payload['accepted'])
   self.assertNotIn('PLANNING_ACCEPTED',result.stdout)
  self.assertIn('small',r.read(self.root/'graph-report.json')['failures'])
  self.assertFalse((self.root/'planning-acceptance.json').exists());self.assertFalse((self.root/'formal.json').exists())
  self.assertEqual((self.root/'topology-state.json').read_bytes(),before)
 def test_cli_disconnected_submission_is_normal_repair_without_mutation(self):
  import json
  self.plan['nodes'].append(scene('isolated',[],'ending','small'))
  p=self.root/'submission.json';r.write(p,self.sub());result=self.cli('submit',p)
  self.assertEqual(result.returncode,0,result.stdout);self.assertEqual(json.loads(result.stdout)['status'],'NEEDS_REPAIR')
  self.assertFalse((self.root/'topology-state.json').exists())
 def test_cli_real_faults_still_fail(self):
  r.submit(self.root,self.sub());r.accept(self.root)
  (self.root/'route-candidate.json').write_text('{}')
  self.assertNotEqual(self.cli('verify').returncode,0)
  (self.root/'topology-state.json').write_text('{broken')
  self.assertNotEqual(self.cli('check').returncode,0)
  (self.root/'topology-state.json').unlink()
  self.assertNotEqual(self.cli('check').returncode,0)
 def test_cli_pass_still_requires_actual_acceptance(self):
  r.submit(self.root,self.sub())
  check=self.cli('check');self.assertEqual(check.returncode,0);self.assertNotIn('PLANNING_ACCEPTED',check.stdout)
  result=self.cli('accept',self.root/'formal.json');self.assertEqual(result.returncode,0,result.stdout)
  self.assertEqual(result.stdout.splitlines()[-1],'PLANNING_ACCEPTED');r.verify(self.root)

class RichnessTests(unittest.TestCase):
 def policy(self):
  return dict(hard_counts={},long_story=True,required_endings=['small','expected','failure','main'],
              forbidden_endings=[],ending_override=False,exemptions={})
 def test_single_woven_module_is_not_whole_graph_growth(self):
  report=g.inspect(woven_fixture(),self.policy())
  self.assertEqual(report['checks']['woven']['status'],'PASS')
  self.assertEqual(report['checks']['sustained_growth']['status'],'FAIL')
 def test_distributed_growth_has_three_successive_stages(self):
  report=g.inspect(rich_fixture(),self.policy())
  self.assertEqual(report['status'],'PASS')
  self.assertGreaterEqual(len(report['checks']['sustained_growth']['evidence']['choices']),4)
  self.assertGreaterEqual(len(report['checks']['sustained_growth']['evidence']['successive_choices']),3)
 def test_same_public_next_choice_does_not_count_as_two_wings(self):
  report=g.inspect(rich_fixture(),self.policy())
  self.assertNotIn('ec',report['checks']['sustained_growth']['evidence']['choices'])
  self.assertNotIn('fc',report['checks']['sustained_growth']['evidence']['choices'])
 def test_one_expected_stop_is_not_a_ladder(self):
  self.assertEqual(g.inspect(woven_fixture(),self.policy())['checks']['ending_ladder']['status'],'FAIL')
 def test_distinct_expected_stops_form_ladder(self):
  report=g.inspect(rich_fixture(),self.policy())
  self.assertTrue(any(e['choices']==['c3','c4'] for e in report['checks']['ending_ladder']['evidence']))
 def test_reusing_one_ending_is_not_two_levels(self):
  p=rich_fixture();next(n for n in p['nodes'] if n['id']=='c4')['options'][0]['target']='expected'
  p['nodes']=[n for n in p['nodes'] if n['id']!='expected2']
  self.assertEqual(g.inspect(p,self.policy())['checks']['ending_ladder']['status'],'FAIL')
 def test_linear_delayed_deaths_do_not_count_as_continuation(self):
  p=rich_fixture()
  for c in ['c1','c2','rc','ec','fc','s','gc','hc']:
   n=next(n for n in p['nodes'] if n['id']==c)
   for k in range(3):
    i=c+'_delay'+str(k);n['options'].append(dict(text='付出代价'+str(k),target=i));p['nodes'].append(scene(i,['bad']))
  rep=g.inspect(p,self.policy());self.assertEqual(rep['checks']['sustained_growth']['status'],'PASS')
  self.assertEqual(rep['checks']['continuation_balance']['status'],'FAIL')
 def test_short_story_has_no_new_richness_hard_gates(self):
  p=self.policy();p['long_story']=False
  report=g.inspect(woven_fixture(),p)
  self.assertEqual(report['status'],'PASS')
 def test_explicit_fixed_shape_can_override_only_selected_defaults(self):
  p=self.policy()
  for k in ['sustained_growth','ending_ladder','continuation_balance']:
   p['exemptions'][k]={'quote':'我就要这张固定图','reason':'保留用户指定结构'}
  report=g.inspect(woven_fixture(),p)
  self.assertEqual(report['status'],'PASS');self.assertEqual(report['checks']['woven']['status'],'PASS')
 def test_new_gate_exemption_still_requires_real_user_quote(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'user-request.md').write_text('我就要三集短故事，两个结局就行。')
   r.write(root/'brief.json',dict(duration_minutes=10,user_overrides={'exemptions':[{'rule':'sustained_growth','quote':'我只要简单图','reason':'固定'}]}))
   with self.assertRaisesRegex(ValueError,'USER_CONSTRAINT'):r.policy(root)

class CompatibilityTests(unittest.TestCase):
 def test_three_episode_two_ending_short_story_needs_no_richness_override(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'user-request.md').write_text('我就要三集短故事，两个结局就行。')
   r.write(root/'brief.json',dict(project_id='short',duration_minutes=10))
   (root/'mainline-story.md').write_text(story([part('a'),part('true')])['complete_story'])
   r.write(root/'mainline.json',story([part('a'),part('true')]))
   (root/'exploration.md').write_text('只测试用户锁定的小图。');r.freeze(root)
   p=dict(nodes=[scene('a',['c']),choice('c',['true','expected']),scene('true',[],'ending','main'),scene('expected',[],'ending','expected')],mainline_path=['a','c','true'])
   r.submit(root,dict(expected_hash=None,reason='用户固定数量',affected_nodes=[],plan=p,branches={'stories':[story([part('expected')])]}))
   r.accept(root);r.verify(root)
   self.assertEqual(r.check(root)['counts'],dict(episode_count=3,choice_node_count=1,ending_count=2,total_node_count=4))
 def test_no_choices_exempts_all_growth_defaults(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'user-request.md').write_text('40分钟，不要选择，一个结局。');r.write(root/'brief.json',dict(duration_minutes=40))
   p=r.policy(root)
   self.assertTrue({'sustained_growth','ending_ladder','continuation_balance'}<=set(p['exemptions']))
 def test_legacy_weaving_failure_can_still_repair_locally(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);quote='40分钟，保留这张图的规模和结算方式，只修交织。'
   (root/'user-request.md').write_text(quote)
   r.write(root/'brief.json',dict(project_id='legacy',duration_minutes=40,user_overrides={'exemptions':[
    dict(rule=k,quote=quote,reason='用户固定现有规模与结算方式') for k in ['sustained_growth','ending_ladder','continuation_balance']]}))
   p=woven_fixture();ids=['a','l','e','j','k','true'];(root/'mainline-story.md').write_text(story([part(i) for i in ids])['complete_story']);r.write(root/'mainline.json',story([part(i) for i in ids]));r.freeze(root)
   (root/'exploration.md').write_text('旧结构局部恢复测试。')
   branches=dict(stories=[story([part(n['id'])]) for n in p['nodes'] if n['kind']!='choice' and n['id'] not in ids])
   f=next(n for n in p['nodes'] if n['id']=='f');f['next']=['small']
   old=r.submit(root,dict(expected_hash=None,plan=p,branches=branches,reason='交织缺口',affected_nodes=[]))
   self.assertIn('woven',old['graph_report']['failures']);before=(root/'mainline.json').read_bytes()
   f['next']=['j'];new=r.submit(root,dict(expected_hash=old['hash'],plan=p,branches=branches,reason='局部修正支线去向',affected_nodes=['f']))
   self.assertEqual(new['graph_report']['status'],'PASS');self.assertEqual((root/'mainline.json').read_bytes(),before)
   r.accept(root);r.verify(root)

if __name__=='__main__':unittest.main()
