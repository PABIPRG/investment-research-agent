"""防止合成夹具字段与正式采集器脱节；不证明真实来源在线。"""
import json
import tempfile
import time
import unittest
from pathlib import Path
from huohuo.execution import Repository
from huohuo.strategies.news_source import source
from huohuo.research_partner.market_sources import collect_market, content_version
from migration_market_fixture import MigrationMarket


class MigrationFixtureTests(unittest.TestCase):
    def test_news_reaches_actual_strategy_collector(self):
        with tempfile.TemporaryDirectory() as folder:
            market = MigrationMarket(Path(folder) / 'control.json')
            self.assertEqual(market.query({'operation':'news'})['data'], market.query({'operation':'news'})['data'])
            repo = Repository(Path(folder) / 'business.sqlite')
            # 策略领域初始化负责其表；不由夹具造表或造事件。
            from huohuo.mandates import Mandates
            from huohuo.strategies.service import Strategies
            core = Mandates(repo, 'fixture')
            Strategies(core.store)
            events = source(market, repo, 'test')([{'code':'600519','name':'贵州茅台'}])
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]['source'], '明确合成来源')
            self.assertIn('仅验证事件', events[0]['summary'])
            self.assertLess(abs(events[0]['observed_at'] - time.time()), 5)
            core.store.close()

    def test_quote_control_changes_source_content_without_changing_clock(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'control.json'; market = MigrationMarket(path)
            scope = {'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'market_quote'}
            first = collect_market(scope, market)
            self.assertEqual(first['values']['items'][0]['price'], 90)
            self.assertEqual(content_version(first), content_version(collect_market(scope, market)))
            path.write_text(json.dumps({'price':110}))
            second = collect_market(scope, market)
            self.assertEqual(second['status'], 'ok')
            self.assertNotEqual(content_version(first), content_version(second))
            path.write_text(json.dumps({'price':None}))
            with self.assertRaises(ValueError): market.query({'operation':'quotes','codes':['600519']})
