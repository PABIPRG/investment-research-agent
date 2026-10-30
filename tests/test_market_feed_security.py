"""公开新闻扩展：XML 不获取外部实体、固定端点、时间/限额不伪造。"""
import unittest
import subprocess
from unittest.mock import patch

from huohuo.market.http import read
from huohuo.market.news_feeds import GOOGLE, google, parse_rss, wallstreetcn


def rss(date='Tue, 27 Oct 2026 10:00:00 +0800', link='https://example.com/news'):
    return f'<rss><channel><item><title>标题 - 原媒体</title><description>正文</description><link>{link}</link><pubDate>{date}</pubDate></item></channel></rss>'


def parse(text):
    return parse_rss(text, provider='google_36kr', source_url=GOOGLE, label='36氪', limit=1)


class FeedSecurityTests(unittest.TestCase):
    def test_source_time_identity_and_unknown_are_stable(self):
        first, second = parse(rss())[0], parse(rss())[0]
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['published_at'], '2026-10-27T02:00:00+00:00')
        self.assertEqual(first['title'], '标题')
        self.assertEqual(first['provider'], 'google_36kr')
        for date in ('unknown', '', 'Tue, 27 Oct 2026 10:00:00'):
            value = parse(rss(date))[0]
            self.assertIsNone(value['published_at'])
            self.assertFalse(value['time_known'])

    def test_external_entities_doctype_bombs_and_oversize_rejected(self):
        values = [
            '<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><channel><item><title>&x;</title></item></channel></rss>',
            '<!DOCTYPE rss SYSTEM "http://127.0.0.1:18841/private"><rss><channel/></rss>',
            '<!DOCTYPE rss [<!ENTITY a "ha"><!ENTITY b "&a;&a;">]><rss><channel/></rss>',
            '<rss>' + 'x' * 2_000_001 + '</rss>',
            '<html><body>captcha</body></html>',
        ]
        for text in values:
            with self.assertRaises(ValueError):
                parse(text)

    def test_fixed_http_hosts_ports_redirects_and_credentials(self):
        for url in ('http://news.google.com/rss/search', 'https://127.0.0.1/feed',
                    'https://news.google.com.evil.example/rss', 'https://user:secret@news.google.com/rss',
                    'https://news.google.com:443/rss'):
            with patch('huohuo.market.http.requests.get') as get, self.assertRaises(ValueError):
                read(url)
            get.assert_not_called()
        with patch('huohuo.market.http.requests.get') as get:
            response = get.return_value.__enter__.return_value
            response.status_code = 302
            with self.assertRaises(ValueError):
                read(GOOGLE)
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
            self.assertNotIn('verify', get.call_args.kwargs)

    def test_google_limits_query_and_never_fetches_article(self):
        with patch('huohuo.market.news_feeds.read', return_value=rss(link='file:///etc/passwd')) as get:
            result = google('36kr', 1)
            self.assertIsNone(result[0]['url'])
            get.assert_called_once_with(GOOGLE, {'q': 'site:36kr.com when:1d', 'hl': 'zh-CN', 'gl': 'CN', 'ceid': 'CN:zh'})
        with patch('huohuo.market.news_feeds.read') as get, self.assertRaises(ValueError):
            google('http://localhost', 1)
        get.assert_not_called()
        self.assertEqual(len(parse_rss('<rss><channel>' + rss().split('<channel>')[1].split('</channel>')[0] * 10 + '</channel></rss>',
                                      provider='ithome', source_url='https://www.ithome.com/rss/', label='IT之家', limit=2)), 2)

    def test_slow_feeds_have_independent_process_deadline(self):
        from huohuo.market.news_feeds import extended_sources
        with patch('huohuo.market.news_feeds.subprocess.run', side_effect=subprocess.TimeoutExpired('feed', 8)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                extended_sources()['google_36kr'](5)
        self.assertEqual(run.call_args.kwargs['timeout'], 8)
        self.assertIn('huohuo.market.news_feeds', run.call_args.args[0])

    def test_wallstreetcn_epoch_and_invalid_payload(self):
        with patch('huohuo.market.news_feeds.read_json', return_value={'data': {'items': [
            {'content_text': '新闻内容', 'display_time': 1793066400, 'uri': 'https://wallstreetcn.com/livenews/1'}]}}):
            result = wallstreetcn(1)
        self.assertTrue(result[0]['time_known'])
        self.assertEqual(result[0]['provider'], 'wallstreetcn')
        with patch('huohuo.market.news_feeds.read_json', return_value={'data': {'items': [{}]}}):
            with self.assertRaises(ValueError):
                wallstreetcn(1)


class FakeResponse:
    status_code = 200

    def __init__(self, body=b'ok'):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.body


class RetryTests(unittest.TestCase):
    """读超时只在显式开启时重试一次；建连失败始终重试一次。"""

    def read(self, *responses, **kwargs):
        with patch('huohuo.market.http.requests.get', side_effect=list(responses)) as get, \
                patch('huohuo.market.http.time.sleep'):
            try:
                return read(GOOGLE, **kwargs), get.call_count
            except Exception as exc:
                return exc, get.call_count

    def test_read_timeout_retried_once_only_when_requested(self):
        import requests
        value, calls = self.read(requests.Timeout('read timed out'), FakeResponse(), retry_timeouts=True)
        self.assertEqual((value, calls), ('ok', 2))
        value, calls = self.read(requests.Timeout('read timed out'), FakeResponse())
        self.assertIsInstance(value, requests.Timeout)
        self.assertEqual(calls, 1)

    def test_retry_never_loops_beyond_one_extra_attempt(self):
        import requests
        value, calls = self.read(requests.Timeout('a'), requests.Timeout('b'), retry_timeouts=True)
        self.assertIsInstance(value, requests.Timeout)
        self.assertEqual(calls, 2)

    def test_connect_errors_retried_by_default(self):
        import requests
        value, calls = self.read(requests.ConnectionError('reset'), FakeResponse(), retry_timeouts=False)
        self.assertEqual((value, calls), ('ok', 2))


if __name__ == '__main__':
    unittest.main()
