"""公开发现处理器 → 持久证据 → 原生确认 → 对象工具；仅替换网络资料。"""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from huohuo.contracts import Invalid
from huohuo.execution import Repository
from huohuo.mandates import Mandates
from huohuo.research_entities.confirmation import EntityConfirmation
from huohuo.research_entities.resolution import DirectoryRepository, resolve
from huohuo.research_entities.tool_bridge import IsolatedToolContext, ResearchToolBridge


class InstrumentConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1800000000
        self.repo = Repository(Path(self.tmp.name) / 'identity.sqlite', clock=lambda: self.now)
        self.core = Mandates(self.repo, 'identity-test')
        self.entities = EntityConfirmation(self.repo, directory=lambda: {
            'rows': [], 'status': 'ok', 'source': {'provider': '合成股票目录'}})
        self.calls = []
        self.funds = [{'基金代码': '513130', '基金简称': '合成恒生科技ETF', '基金类型': '指数型-股票'}]
        self.bond = {'SECURITY_CODE': '127119', 'SECURITY_NAME_ABBR': '合成转债',
                     'CONVERT_STOCK_CODE': '000001', 'SECUCODE': '127119.SZ'}
        self.bridge = ResearchToolBridge(self.repo, self.entities, context_factory=self.context)

    def tearDown(self):
        self.core.store.close()
        self.tmp.cleanup()

    def context(self, repository):
        ctx = IsolatedToolContext(repository)
        ctx.call_akshare = self.provider
        ctx._now = lambda: datetime(2026, 10, 28, tzinfo=timezone.utc)
        return ctx

    def provider(self, name, **args):
        self.calls.append((name, args))
        if name == 'fund_name_em':
            return pd.DataFrame(self.funds)
        if name == 'bond_zh_cov_info':
            return pd.DataFrame([self.bond])
        if name in ('fund_etf_hist_sina', 'fund_open_fund_info_em'):
            return pd.DataFrame([{'date': '2026-10-27', 'close': 1.23}])
        if name == 'tool_trade_date_hist_sina':
            return pd.DataFrame({'trade_date': pd.bdate_range('2026-01-01', '2026-12-31').date})
        raise AssertionError(f'意外资料请求: {name}')

    def choose(self, query, eid, user='alice', session='chat'):
        snap = self.entities.resolve(user, session, query)
        mention = next(m for m in snap['mentions'] if eid in m['candidate_entity_ids'])
        return self.entities.confirm(user, session, snap['snapshot_id'], snap['version'],
            {mention['mention_id']: eid}, 'native-answer')['confirmations'][0]

    def test_known_etf_numeric_identifier_and_exchange_survive_confirmation(self):
        for code, exchange in [('510300', 'SSE'), ('159919', 'SZSE'), ('588000', 'SSE')]:
            eid = next(e.entity_id for e in DirectoryRepository([]).entities.values()
                       if e.entity_id.endswith(':' + code))
            confirmed = self.choose(code, eid)
            self.assertEqual(confirmed['identifiers']['fund_code'], code)
            self.assertEqual(confirmed['identifiers']['exchange'], exchange)
            self.assertEqual(confirmed['operations'], ['quote_snapshot'])
            self.assertEqual(confirmed['execution_entity_id'],'FUND:CN:'+code)

    def test_numeric_collision_preserves_index_and_stock_until_native_selection(self):
        result = resolve('000300', {'rows': [{'code': '000300', 'name': '合成同码证券'}],
                                  'status': 'ok', 'source': {'provider': '合成碰撞目录'}})
        ids = {x['entity_id'] for x in result['candidates']}
        self.assertIn('INDEX:CSI300', ids)
        self.assertIn('SEC:CN:A:000300', ids)
        self.assertTrue(result['requires_confirmation'])

    def test_fund_discovery_result_becomes_candidate_without_auto_confirmation(self):
        result = self.bridge.run('alice', 'chat', 'find-fund', 'fund_lookup', {'code': '513130'})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(self.entities.current('alice', 'chat'), [])
        confirmed = self.choose('513130', 'FUND:513130')
        self.assertEqual(confirmed['identifiers']['fund_code'], '513130')
        self.assertIn('fund_name_em', confirmed['source_evidence']['source'])
        self.assertEqual(confirmed['source_evidence']['evidence_id'], result['evidence_id'])
        with self.assertRaises(Invalid):
            self.bridge.run('alice', 'chat', 'wrong-stock-tool', 'quote_history',
                            {'confirmation_id': confirmed['confirmation_id']})

    def test_bond_discovery_native_confirmation_then_terms_uses_exact_identity(self):
        result = self.bridge.run('alice', 'chat', 'find-bond', 'convertible_bond_lookup', {'code': '127119'})
        self.assertEqual(result['status'], 'ok')
        confirmed = self.choose('127119', 'BOND:127119')
        self.assertEqual(confirmed['identifiers']['exchange'], 'SZSE')
        self.assertEqual(confirmed['operations'], [])
        terms = self.bridge.run('alice', 'chat', 'terms', 'bond_terms_lookup',
                                {'confirmation_id': confirmed['confirmation_id']})
        self.assertEqual(terms['status'], 'ok')
        self.assertEqual(terms['data']['code'], '127119')
        pronoun = self.entities.resolve('alice', 'chat', '它的条款呢')
        self.assertFalse(pronoun['requires_confirmation'])
        self.assertEqual(pronoun['entity_details']['BOND:127119']['identifiers']['exchange'], 'SZSE')
        with self.assertRaises(Invalid):
            self.bridge.run('alice', 'chat', 'bond-as-fund', 'fund_holdings_lookup',
                            {'confirmation_id': confirmed['confirmation_id']})

    def test_discovery_cannot_cross_user_session_or_expiry(self):
        self.bridge.run('alice', 'chat', 'find-bond', 'convertible_bond_lookup', {'code': '127119'})
        for user, session in [('bob', 'chat'), ('alice', 'other')]:
            self.assertFalse(self.entities.resolve(user, session, '127119')['candidates'])
        self.now += 3601
        self.assertFalse(self.entities.resolve('alice', 'chat', '127119')['candidates'])

    def test_partial_fund_name_from_successful_discovery_is_an_alias_not_identity(self):
        self.bridge.run('alice', 'chat', 'fund-name', 'fund_lookup', {'name': '恒生科技'})
        confirmed = self.choose('研究恒生科技', 'FUND:513130')
        self.assertEqual(confirmed['label'], '合成恒生科技ETF')
        self.assertNotIn('exchange', confirmed['identifiers'])

    def test_snapshot_cannot_extend_discovery_lifetime_or_accept_forged_selection(self):
        self.bridge.run('alice', 'chat', 'find-bond', 'convertible_bond_lookup', {'code': '127119'})
        self.now += 3500
        snap = self.entities.resolve('alice', 'chat', '127119')
        mention = snap['mentions'][0]['mention_id']
        with self.assertRaises(Invalid):
            self.entities.confirm('alice', 'chat', snap['snapshot_id'], snap['version'],
                                  {mention: 'BOND:000001'}, 'forged-answer')
        self.now += 101
        with self.assertRaises(Invalid):
            self.entities.confirm('alice', 'chat', snap['snapshot_id'], snap['version'],
                                  {mention: 'BOND:127119'}, 'late-answer')

    def test_discovery_is_usable_if_unrelated_stock_directory_fails(self):
        self.bridge.run('alice', 'chat', 'find-bond', 'convertible_bond_lookup', {'code': '127119'})
        self.entities.directory = lambda: {'rows': [{'code': '600519', 'name': '过期股票'}],
                                          'status': 'unavailable', 'source': {}}
        snap = self.entities.resolve('alice', 'chat', '127119 与过期股票')
        self.assertEqual(snap['provider_status'], 'ok')
        self.assertEqual([c['entity_id'] for c in snap['candidates']], ['BOND:127119'])

    def test_wrong_source_shape_does_not_create_fund_identity(self):
        self.funds = [{'基金代码': '513130', 'SECURITY_NAME_ABBR': '错误种类'}]
        self.bridge.run('alice', 'chat', 'bad-fund', 'fund_lookup', {'code': '513130'})
        self.assertFalse(self.entities.resolve('alice', 'chat', '513130')['candidates'])

    def test_known_etf_routes_by_confirmed_market(self):
        for code, symbol in [('510300', 'sh510300'), ('159919', 'sz159919')]:
            confirmed = self.choose(code, f'FUND:CSI300ETF:{code}')
            result = self.bridge.run('alice', 'chat', 'returns-' + code, 'fund_performance_lookup',
                                    {'confirmation_id': confirmed['confirmation_id'], 'days': 7, 'limit': 3})
            self.assertEqual(result['status'], 'ok')
            self.assertEqual([x for x in self.calls if x[0].startswith('fund_')][-1],
                             ('fund_etf_hist_sina', {'symbol': symbol}))
            self.assertEqual(result['source'], 'akshare.fund_etf_hist_sina')

    def test_open_fund_does_not_infer_stock_market_from_numeric_code(self):
        self.funds = [{'基金代码': '000001', '基金简称': '合成开放式基金', '基金类型': '混合型'}]
        self.bridge.run('alice', 'chat', 'open-fund', 'fund_lookup', {'code': '000001'})
        confirmed = self.choose('000001', 'FUND:000001')
        self.assertNotIn('exchange', confirmed['identifiers'])
        self.bridge.run('alice', 'chat', 'open-nav', 'fund_performance_lookup',
                        {'confirmation_id': confirmed['confirmation_id'], 'days': 7})
        self.assertEqual([x for x in self.calls if x[0].startswith('fund_')][-1][0], 'fund_open_fund_info_em')


if __name__ == '__main__':
    unittest.main()
