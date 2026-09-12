import copy
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'business-skill-track/episode-skill-split/versions/0.20/episode-route-planner-biz/scripts'
sys.path.insert(0, str(SCRIPTS))
import canvas_writing as cw


def node(ref, kind='video'):
    return {'node_ref':ref,'node_type':kind,'title':ref,'summary':'人在山道守候来客。',
            'content':{'conflict':'等待援助','objective':'守在门外','script':{'text':''}},
            'interaction':{'question':'前往哪里？' if kind=='choice' else None},
            'metadata':{'is_ending':ref in {'episode-003','episode-009'},'ending_type':None},'assets':{}}


def fixture():
    return {'schema_version':'nextplay.route.v1','identity':{'story_id':'test'},'revision':4,
            'data':{'route_ref':'route','entry_node_ref':'episode-001',
                    'nodes':[node('episode-001'),node('episode-002','choice'),node('episode-003'),node('episode-009')],
                    'edges':[{'edge_ref':'e1','source_node_ref':'episode-001','target_node_ref':'episode-002','edge_type':'default'},
                             {'edge_ref':'e2','source_node_ref':'episode-002','target_node_ref':'episode-003','edge_type':'choice','choice':{'label':'向北走'}},
                             {'edge_ref':'e3','source_node_ref':'episode-002','target_node_ref':'episode-009','edge_type':'choice','choice':{'label':'向南走'}}]}}


def material():
    return {'单集梗概':'人在山道守候来客。','本集冲突':'等待援助','stop_boundary':'守在门外',
            'entry_state':{},'state_changes':{},'allowed_characters':[],'allowed_scenes':[],'allowed_props':[]}


class CanvasWritingTests(unittest.TestCase):
    def setUp(self):
        self.c=fixture(); self.state=cw.confirm(self.c,cw.fingerprint(self.c),'record')
    def test_first_observation_asks(self): self.assertTrue(cw.observe(self.c,{})['ask_user'])
    def test_same_edit_batch_does_not_reask(self): self.assertFalse(cw.observe(self.c,self.state)['ask_user'])
    def test_new_deletion_asks_and_invalidates_answer(self):
        self.c['data']['nodes'].pop()
        self.assertTrue(cw.observe(self.c,self.state)['ask_user'])
        with self.assertRaisesRegex(ValueError,'CHANGED_SINCE_QUESTION'): cw.confirm(self.c,self.state['fingerprint'],'direct')
    def test_media_screenplay_revision_layout_do_not_reask(self):
        self.c['revision']+=1;n=self.c['data']['nodes'][0];n['content']['script']['text']='成稿';n['timeline']={'clips':[{}]};n['position']={'x':8};n['display_number']=99
        self.assertFalse(cw.observe(self.c,self.state)['ask_user'])
    def test_title_edit_reasks(self):
        self.c['data']['nodes'][0]['title']='另一个标题';self.assertTrue(cw.observe(self.c,self.state)['ask_user'])
    def test_isolated_episode_is_rejected_without_mutating_canvas(self):
        self.c['data']['edges'].pop();original=copy.deepcopy(self.c)
        state=cw.confirm(self.c,cw.fingerprint(self.c),'stop')
        with self.assertRaises(ValueError): cw.build(self.c,state,'episode-009',material())
        self.assertEqual(self.c,original)
        self.assertTrue(any('孤立' in x for x in cw.graph_issues(self.c)))
    def test_dangling_option_is_rejected_not_silently_filtered(self):
        self.c['data']['edges'][-1]['target_node_ref']='deleted'
        with self.assertRaisesRegex(ValueError,'CURRENT_GRAPH_REPAIR_REQUIRED'): cw.confirm(self.c,cw.fingerprint(self.c),'record')
        self.assertTrue(any('连线目标不存在' in x for x in cw.graph_issues(self.c)))
    def test_two_actual_directions_preserve_choice(self):
        route,_=cw.build(self.c,self.state,'episode-001',material());self.assertTrue(route['nodes'][1]['互动节点']['是否有选择问题'])
    def test_both_repair_answers_require_saved_readback(self):
        for action in ('direct','transition'):
            state=cw.confirm(self.c,cw.fingerprint(self.c),action)
            with self.assertRaisesRegex(ValueError,'COMPLETE_AUTHORIZED_REPAIR'): cw.build(self.c,state,'episode-001',material())
    def test_stopped_broken_canvas_needs_new_decision_on_resume(self):
        self.c['data']['edges'].pop();state=cw.confirm(self.c,cw.fingerprint(self.c),'stop')
        self.assertTrue(cw.observe(self.c,state)['ask_user'])
    def test_obsolete_keep_permission_does_not_bypass_new_gate(self):
        old=copy.deepcopy(self.state);old.pop('policy');old['action']='keep'
        self.assertTrue(cw.observe(self.c,old)['ask_user'])
        with self.assertRaises(ValueError): cw.build(self.c,old,'episode-001',material())
    def test_previous_deleted_ref_is_not_recreated_in_projection(self):
        self.c['data']['nodes']=[n for n in self.c['data']['nodes'] if n['node_ref']!='episode-002']
        self.c['data']['edges']=[{'edge_ref':'new','source_node_ref':'episode-001','target_node_ref':'episode-003','edge_type':'default'}]
        self.c['data']['nodes']=[n for n in self.c['data']['nodes'] if n['node_ref']!='episode-009']
        state=cw.confirm(self.c,cw.fingerprint(self.c),'record');r,_=cw.build(self.c,state,'episode-001',material())
        self.assertNotIn('episode-002',[n['node_id'] for n in r['nodes']])
        self.assertFalse(r['nodes'][0]['互动节点']['是否有选择问题'])
    def test_changed_canvas_blocks_save(self):
        r,p=cw.build(self.c,self.state,'episode-001',material());self.c['data']['edges'].pop()
        with self.assertRaisesRegex(ValueError,'CURRENT_CANVAS_CHANGED'):cw.verify(self.c,r,p)
    def test_changed_material_blocks_save(self):
        r,p=cw.build(self.c,self.state,'episode-001',material());r['nodes'][0]['route_material']['单集梗概']='偷偷修改'
        with self.assertRaisesRegex(ValueError,'WRITING_SNAPSHOT_CHANGED'):cw.verify(self.c,r,p)
    def test_unrelated_script_write_keeps_material_valid(self):
        r,p=cw.build(self.c,self.state,'episode-001',material());self.c['data']['nodes'][-1]['content']['script']['text']='新剧本';self.c['revision']+=1
        self.assertEqual(cw.verify(self.c,r,p)['status'],'CURRENT_NODE_MATERIAL_VALID')
    def test_stable_ids_do_not_get_renumbered(self):
        r,_=cw.build(self.c,self.state,'episode-009',material());self.assertEqual([n['node_id'] for n in r['nodes']],[n['node_ref'] for n in self.c['data']['nodes']])
    def test_writer_contract_and_index_accept_current_snapshot(self):
        writer=ROOT/'business-skill-track/episode-skill-split/versions/0.16/episode-screenwriter-biz/scripts';sys.path.insert(0,str(writer))
        import screenplay_contract, episode_plan_index
        route,_=cw.build(self.c,self.state,'episode-009',material())
        self.assertEqual(screenplay_contract.formal_route_issues(route),[])
        index=episode_plan_index.build_index(route);self.assertEqual(episode_plan_index.validate_index(route,index),[])

if __name__=='__main__': unittest.main()
