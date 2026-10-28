"""扩展资料源回归：来源覆盖、显式授权、部分失败、有限值。"""
import unittest
from unittest.mock import patch

from huohuo.contracts import Invalid
from huohuo.market.contracts import validate
from huohuo.market.news import fetch_news, item
from huohuo.market.technical import fetch_technical


def record(provider):
    return item(provider, '正文', f'https://example.com/{provider}', '2026-10-27 10:00:00',
                provider, provider=provider, source_url='https://example.com/feed')


class NewsExpansionTests(unittest.TestCase):
    def test_contract_requires_explicit_boolean_and_rejects_targeted_mix(self):
        self.assertFalse(validate({'operation': 'news'})['include_slow'])
        self.assertTrue(validate({'operation': 'brief', 'codes': ['600519'], 'period': 'pre',
                                  'include_slow': True})['include_slow'])
        for args in ({'include_slow': 'yes'}, {'code': '600519', 'include_slow': True}, {'url': 'http://127.0.0.1'}):
            with self.assertRaises(Invalid):
                validate({'operation': 'news', **args})

    def test_default_fast_and_explicit_full_preserve_each_source_result(self):
        with patch('huohuo.market.news.sina', return_value=[record('sina')]), \
             patch('huohuo.market.news.cls', return_value=[]), \
             patch('huohuo.market.news.extended_sources', return_value={'wallstreetcn': lambda _: [record('wallstreetcn')]}) as extra:
            fast = fetch_news({'limit': 5})
            extra.assert_not_called()
            self.assertEqual(fast['data']['tier'], 'fast')
            full = fetch_news({'limit': 5, 'include_slow': True})
        self.assertTrue(full['complete'])
        self.assertEqual(full['data']['tier'], 'extended')
        self.assertEqual({s['source']: s['status'] for s in full['data']['sources']},
                         {'sina': 'ok', 'cls': 'empty', 'wallstreetcn': 'ok'})

    def test_extended_failure_is_not_silently_complete(self):
        def unavailable(_):
            raise TimeoutError('timeout')
        with patch('huohuo.market.news.sina', return_value=[]), patch('huohuo.market.news.cls', return_value=[]), \
             patch('huohuo.market.news.extended_sources', return_value={'google_36kr': unavailable}):
            result = fetch_news({'include_slow': True, 'limit': 1})
        self.assertEqual(result['status'], 'empty')
        self.assertFalse(result['complete'])
        self.assertEqual(result['data']['sources'][-1]['status'], 'unavailable')

    def test_brief_passes_include_slow_without_new_scheduler(self):
        from huohuo.market.provider import brief
        from huohuo.market.contracts import envelope
        with patch('huohuo.market.provider.fetch_quotes', return_value=envelope('q', {})), \
             patch('huohuo.market.provider.fetch_news', return_value=envelope('n', {})) as news:
            brief({'codes': ['600519'], 'period': 'pre', 'include_slow': True})
        news.assert_called_once_with({'limit': 20, 'include_slow': True})


class ThirdDailyFallbackTests(unittest.TestCase):
    def test_baostock_third_fallback_preserves_date_adjustment_units(self):
        bars = [{'date': f'2026-09-{i:02}', 'open': 10, 'high': 11, 'low': 9, 'close': 10,
                 'volume': 1234, 'amount': 12340} for i in range(1, 21)]
        with patch('huohuo.market.technical.eastmoney', side_effect=TimeoutError), \
             patch('huohuo.market.technical.sina', side_effect=ValueError), \
             patch('huohuo.market.technical.baostock', return_value=bars):
            result = fetch_technical({'code': '600519', 'lookback': 20})
        self.assertEqual(result['source'], 'baostock')
        self.assertEqual(result['data']['adjustment'], 'qfq')
        self.assertEqual(result['data']['transport'], 'plain_tcp_public')
        self.assertEqual(result['data']['through'], '2026-09-20')
        self.assertEqual(result['data']['bars'][0]['volume'], 1234)
        self.assertEqual(result['data']['units']['amount'], 'CNY')
        self.assertTrue(result['complete'])

    def test_successful_sina_does_not_trigger_third_source(self):
        bars = [{'date': '2026-09-01', 'open': 10, 'high': 11, 'low': 9, 'close': 10,
                 'volume': 1234, 'amount': None}]
        with patch('huohuo.market.technical.eastmoney', return_value=[]), \
             patch('huohuo.market.technical.sina', return_value=bars), \
             patch('huohuo.market.technical.baostock') as third:
            result = fetch_technical({'code': '600519', 'lookback': 20})
        third.assert_not_called()
        self.assertEqual(result['source'], 'sina')
        self.assertFalse(result['complete'])

    def test_all_sources_fail_and_nan_are_not_valid_evidence(self):
        for rows in ([], [{'date': '2026-09-01', 'open': float('nan'), 'high': 11, 'low': 9, 'close': 10}]):
            with patch('huohuo.market.technical.eastmoney', return_value=[]), \
                 patch('huohuo.market.technical.sina', side_effect=TimeoutError), \
                 patch('huohuo.market.technical.baostock', return_value=rows):
                result = fetch_technical({'code': '600519', 'lookback': 20})
            self.assertEqual(result['status'], 'unavailable')
            self.assertFalse(result['complete'])


if __name__ == '__main__':
    unittest.main()
