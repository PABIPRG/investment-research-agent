"""真实HTTP分派，合成来源；内部接口不能靠客户端标记越权。"""
import unittest
import test_api as fixtures
from test_market_integration import Market, SCOPE


class PriceWorkerApi(unittest.TestCase):
    setUp = fixtures.ApiTests.setUp
    tearDown = fixtures.ApiTests.tearDown
    call = fixtures.ApiTests.call

    def test_claim_routes_formal_price_and_endpoint_checks_capability(self):
        core = self.service.mandates
        core.entities.directory = lambda: {'status': 'ok', 'rows': [{'code': '600519', 'name': '贵州茅台'}], 'source': {'provider': 'synthetic'}}
        self.service.market.query = Market().query
        r = core.entities.resolve('owner', 'test', '600519行情')
        c = core.entities.confirm('owner', 'test', r['snapshot_id'], r['version'], {r['mentions'][0]['mention_id']: SCOPE['entity_id']}, 'synthetic')
        core.create('owner', {'request_key': 'create-price-api', 'scope': SCOPE, 'goal': '合成到价提醒', 'contact_note': '仅应用内', 'session_id': 'test',
                             'confirmation_id': c['confirmations'][0]['confirmation_id'], 'contact_rule': {'mode': 'condition', 'condition': {'type': 'numeric', 'metric': 'price', 'operator': '>', 'threshold': 100}}})
        status, job = self.call('/worker/claim', {'worker_id': 'api-test', 'admission_policy': 'hook-model-gate-v1'}, 'worker-secret')
        self.assertEqual(status, 200); self.assertTrue(job['price_rule'])
        path = '/worker/attempts/'+job['attempt_id']+'/price-run'
        self.assertEqual(self.call(path, {}, 'user-secret', {'X-Attempt-Token': job['lease_token']})[0], 403)
        self.assertEqual(self.call(path, {}, 'worker-secret', {'X-Attempt-Token': 'forged'})[0], 409)
        first = self.call(path, {}, 'worker-secret', {'X-Attempt-Token': job['lease_token']})
        self.assertEqual(first[0], 200, first); self.assertEqual(first[1]['status'], 'succeeded')
        self.assertEqual(first, self.call(path, {}, 'worker-secret', {'X-Attempt-Token': job['lease_token']}))
        self.call('/executions', {'request_key': 'unbound-price-api', 'scope': SCOPE, 'question': '仅当场研究'})
        _, other = self.call('/worker/claim', {'worker_id': 'api-test', 'admission_policy': 'hook-model-gate-v1'}, 'worker-secret')
        self.assertNotIn('price_rule', other)
        self.assertEqual(self.call('/worker/attempts/'+other['attempt_id']+'/price-run', {}, 'worker-secret', {'X-Attempt-Token': other['lease_token']})[0], 400)
