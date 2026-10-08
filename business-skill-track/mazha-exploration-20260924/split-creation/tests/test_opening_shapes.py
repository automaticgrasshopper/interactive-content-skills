import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/mazha-outline-route-1008/scripts/inspect_opening.py'
spec = importlib.util.spec_from_file_location('opening_shapes', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def route(edges, choices=('q',), endings=()):
    refs = sorted({n for e in edges for n in e})
    return {'schema_version': 'nextplay.route.v1', 'revision': 1, 'data': {
        'entry_node_ref': 'intro',
        'nodes': [{'node_ref': n, 'node_type': 'choice' if n in choices else 'video',
                   'title': '任意标题', 'metadata': {'is_ending': n in endings}} for n in refs],
        'edges': [{'source_node_ref': a, 'target_node_ref': b} for a, b in edges]}}


BASE = [('intro', 'q'), ('q', 'a'), ('q', 'b')]


class OpeningShapes(unittest.TestCase):
    def test_six_distinct_topologies(self):
        fixtures = [
            (1, route(BASE)),
            (2, route(BASE + [('a', 'm'), ('b', 'm')])),
            (3, route(BASE, endings=('a',))),
            (4, route(BASE + [('a', 'qa'), ('qa', 'a1'), ('qa', 'a2')], ('q', 'qa'))),
            (5, route(BASE + [('a', 'qa'), ('b', 'qb'), ('qa', 'a1'), ('qa', 'a2'),
                             ('qb', 'b1'), ('qb', 'b2')], ('q', 'qa', 'qb'))),
            (6, route(BASE + [('a', 'qa'), ('b', 'qb'), ('qa', 'x'), ('qa', 'y'),
                             ('qb', 'x'), ('qb', 'y'), ('x', 'm'), ('y', 'm')], ('q', 'qa', 'qb'))),
        ]
        for expected, data in fixtures:
            with self.subTest(shape=expected):
                self.assertEqual(module.inspect(data)['shape_ids'], [expected])

    def test_titles_and_longer_straight_arms_do_not_fake_deeper_shape(self):
        data = route(BASE + [('a', 'a2'), ('a2', 'm'), ('b', 'b2'), ('b2', 'm')])
        for node in data['data']['nodes']:
            node['title'] = '双翼展开、双线交织'
        self.assertEqual(module.inspect(data)['shape_ids'], [2])

    def test_two_serial_common_scenes_are_not_woven(self):
        data = route(BASE + [('a', 'qa'), ('b', 'qb'), ('qa', 'a1'), ('qa', 'a2'),
                            ('qb', 'b1'), ('qb', 'b2'), ('a1', 'x'), ('a2', 'x'),
                            ('b1', 'x'), ('b2', 'x'), ('x', 'y')], ('q', 'qa', 'qb'))
        self.assertEqual(module.inspect(data)['shape_ids'], [5])

    def test_bad_readback_is_rejected(self):
        for edges in [BASE + [('a', 'intro')], BASE + [('outside', 'orphan')]]:
            with self.assertRaises(ValueError):
                module.inspect(route(edges))
        data = route(BASE)
        data['data']['edges'].append({'source_node_ref': 'a', 'target_node_ref': 'missing'})
        with self.assertRaises(ValueError):
            module.inspect(data)

    def test_expectation_mismatch_fails_and_never_writes_route(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'route.json'
            path.write_text(json.dumps(route(BASE + [('a', 'm'), ('b', 'm')]), ensure_ascii=False))
            original = path.read_bytes()
            result = subprocess.run([sys.executable, str(SCRIPT), str(path), '--expect', '4'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['status'], 'SHAPE_MISMATCH')
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
