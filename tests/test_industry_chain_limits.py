import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from huohuo.contracts import Invalid
from huohuo.execution import Conflict
from huohuo.industry_chain.seed import SeedData
from huohuo.industry_chain.overlay import validate_overlay
from huohuo.industry_chain.universe_source import fetch_universe
from test_industry_chain_fixtures import Fixture, Source, Response, dataset, overlay


class IndustryChainLimitTests(unittest.TestCase):
    def test_file_total_redirect_json_and_structure_rejected(self):
        cases = [
            (lambda url, **kw: Response(b'{}', declared=1001), {'max_file': 1000}),
            (lambda url, **kw: Response(b'x'*1001, declared=1), {'max_file': 1000}),
            (Source(), {'max_total': 150}),
            (lambda url, **kw: Response({}, status=302), {}),
            (lambda url, **kw: Response(b'not-json'), {}),
            (lambda url, **kw: Response(b'{"companies":NaN}'), {}),
            (lambda url, **kw: Response({}), {}),
        ]
        for get, limits in cases:
            with self.subTest(limits=limits), tempfile.TemporaryDirectory() as directory:
                seed = SeedData(directory, http_get=get, **limits)
                with self.assertRaises(ValueError): seed.download('operation')
                self.assertFalse(seed.status()['available'])
                self.assertFalse(list(Path(directory).glob('.staging-*')))
                self.assertFalse((Path(directory)/'CURRENT.json').exists())

    def test_failed_atomic_publication_keeps_previous_data(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Source()
            seed = SeedData(directory, http_get=source)
            seed.download('old')
            previous = seed.current()
            source.data = dataset('new')
            with patch('huohuo.industry_chain.seed.atomic_json', side_effect=OSError('simulated disk error')):
                with self.assertRaises(OSError): seed.download('new', refresh=True)
            self.assertEqual(seed.current(), previous)
            self.assertTrue(seed.status()['available'])
            self.assertEqual(len(list(Path(directory).glob('seed-*'))), 1)

    def test_corrupt_file_invalidates_previous_ready_and_can_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            seed = SeedData(directory, http_get=Source())
            seed.download('a')
            (seed.data_path()/'companies.json').write_text('[]')
            self.assertEqual(seed.status()['state'], 'error')
            seed.download('b', refresh=True)
            self.assertEqual(seed.status()['state'], 'ready')

    def test_pending_download_rejects_duplicate_operation_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            ready, release = threading.Event(), threading.Event()
            source = Source()
            def get(url, **kwargs):
                ready.set()
                release.wait(3)
                return source(url, **kwargs)
            seed = SeedData(directory, http_get=get)
            worker = threading.Thread(target=lambda: seed.download('one'))
            worker.start()
            try:
                self.assertTrue(ready.wait(2))
                self.assertEqual(seed.status()['state'], 'downloading')
                with self.assertRaises(RuntimeError): seed.download('two')
                with self.assertRaises(RuntimeError): seed.delete('three')
            finally:
                release.set(); worker.join(4)
            self.assertFalse(worker.is_alive())
            self.assertEqual(len(source.calls), 5)
            self.assertEqual(seed.status()['state'], 'ready')

    def test_overlay_rejects_invalid_inference_schema_and_evidence(self):
        value = overlay()
        value['companies'][0]['materials'][0]['suppliers'][0]['share'] = 20
        with self.assertRaises(Invalid): validate_overlay(value)
        value = overlay()
        value['companies'][0]['materials'][0]['suppliers'][0]['confidence'] = float('nan')
        with self.assertRaises(Invalid): validate_overlay(value)
        value = overlay(); value['shell'] = 'anything'
        with self.assertRaises(Invalid): validate_overlay(value)
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)
            fixture.install(); fixture.evidence()
            preview = fixture.preview('overlay', overlay())
            fixture.evidence(status='error')
            receipt = fixture.commit(preview)
            self.assertEqual(receipt['status'], 'failed')
            self.assertEqual(fixture.service.status('p')['overlay_revision'], 0)

    def test_universe_complete_snapshot_and_missing_coordinates(self):
        rows = [{'f12': '600001', 'f14': '核心甲', 'f100': '工业', 'f20': 100000000}, {'f12': '600002', 'f14': '供应乙', 'f100': '工业', 'f20': '-'}]
        def get(url, **kwargs): return Response({'data': {'total': 2, 'diff': rows}})
        self.assertEqual(fetch_universe(get)[0]['market_cap'], 1)
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)
            fixture.install(); fixture.service.http_get = get
            receipt = fixture.commit(fixture.preview('refresh_universe'))
            self.assertEqual(receipt['status'], 'committed')
            graph = fixture.service.query('p', '/graph/network', {'include_universe': True, 'min_share': 0})
            self.assertEqual(graph['stats']['total_nodes'], 2)
            self.assertEqual(graph['nodes'][0]['market_cap_cny'], 100000000)
            self.assertIsInstance(graph['nodes'][0]['init_x'], (float, int))
            self.assertEqual(graph['links'][0]['share'], 0)
            self.assertEqual(graph['links'][0]['share_source'], 'disclosed')
            self.assertEqual(receipt['data']['universe_companies'], 2)

    def test_universe_rejects_duplicate_or_partial_snapshot(self):
        for payload in ({'data': {'total': 2, 'diff': []}}, {'data': {'total': 2, 'diff': [{'f12': '600001', 'f14': '甲'}, {'f12': '600001', 'f14': '甲'}]}}, {'data': {'total': 10001, 'diff': []}}):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError): fetch_universe(lambda *a, **kw: Response(payload))

    def test_request_reuse_cannot_change_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(directory)
            preview = fixture.preview()
            body = {'request_key': preview['request_key'], 'action': 'delete', 'payload': {}}
            with self.assertRaises(Conflict): fixture.service.prepare('p', 's', body)
            self.assertEqual(fixture.source.calls, [])
