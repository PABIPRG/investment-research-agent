import unittest
from unittest.mock import patch
from huohuo.research_entities.security_search import search, reset_cache
from huohuo.research_entities import security_search
from huohuo.contracts import Invalid

ROWS=[{'code':'002518','name':'科士达'},{'code':'002519','name':'科士达测试'},{'code':'600519','name':'贵州茅台'},{'code':'510300','name':'沪深300ETF'},{'code':'920001','name':'北交测试'}]
class SearchTests(unittest.TestCase):
 def setUp(self): reset_cache()
 def test_exact_first_and_confirmation(self):
  r=search('科士达',lambda:ROWS)
  self.assertEqual(r['status'],'ok');self.assertEqual([x['code'] for x in r['candidates']],['002518','002519'])
  self.assertEqual(r['candidates'][0]['exchange'],'SZSE');self.assertTrue(r['requires_confirmation'])
 def test_no_match_is_not_failure(self):
  self.assertEqual(search('未知公司',lambda:ROWS)['status'],'empty')
 def test_failure_is_not_empty(self):
  def fail():raise TimeoutError()
  self.assertEqual(search('科士达',fail)['status'],'unavailable')
 def test_empty_catalog_is_unavailable(self):
  self.assertEqual(search('科士达',lambda:[])['status'],'unavailable')
 def test_codes_filter_unsupported(self):
  self.assertEqual(len(search('0025',lambda:ROWS)['candidates']),2)
  self.assertEqual(search('ETF',lambda:ROWS)['status'],'empty')
 def test_cache_and_stale_failure(self):
  search('科士达',lambda:ROWS,now=100)
  def fail():raise TimeoutError()
  self.assertEqual(search('科士达',fail,now=101)['status'],'ok')
  with patch('huohuo.research_entities.security_search.suggest',side_effect=TimeoutError()):
   r=search('科士达',fail,now=4000)
  self.assertEqual(r['status'],'stale');self.assertTrue(r['candidates']);self.assertFalse(r['usable_for_confirmation'])
 def test_fallback_uses_real_source_and_does_not_cache_partial_directory(self):
  with patch('huohuo.research_entities.security_search.load_catalog',side_effect=TimeoutError()), patch('huohuo.research_entities.security_search.suggest',return_value=ROWS[:1]):
   r=search('科士达')
   self.assertEqual(r['status'],'ok');self.assertEqual(r['source']['provider'],'腾讯证券搜索')
  self.assertEqual(search('茅台',lambda:ROWS)['candidates'][0]['code'],'600519')
 def test_failed_catalog_load_backs_off_instead_of_retrying_every_search(self):
  with patch('huohuo.research_entities.security_search.suggest',side_effect=TimeoutError()), patch('huohuo.research_entities.security_search.load_catalog',side_effect=TimeoutError()) as load:
   self.assertEqual(search('科士达',now=1000)['status'],'unavailable')
   self.assertEqual(search('科士达',now=1001)['status'],'unavailable')
  self.assertEqual(load.call_count,1)
 def test_name_search_prefers_fast_suggestion_without_catalog(self):
  with patch('huohuo.research_entities.security_search.suggest',return_value=ROWS[:2]), patch('huohuo.research_entities.security_search.load_catalog') as load:
   r=search('科士达')
  self.assertEqual(r['status'],'ok');self.assertEqual(r['source']['provider'],'腾讯证券搜索')
  load.assert_not_called()
 def test_bad_query(self):
  for q in ['',None,'x'*101]:
   with self.assertRaises(Invalid):search(q,lambda:ROWS)
 def test_suggest_parses_smartbox_and_keeps_only_a_shares(self):
  class Reply:
   text=r'v_hint="sh~600519~贵州茅台~gzmt~GP-A^hk~03750~宁德时代~ndsd~GP^sz~300750~宁德时代~ndsd~GP-A^sh~510300~沪深300ETF~hs300~ETF"'
   def raise_for_status(self):pass
  with patch('requests.get',return_value=Reply()):
   rows=security_search.suggest('茅台')
  self.assertEqual(rows,[{'code':'600519','name':'贵州茅台'},{'code':'300750','name':'宁德时代'}])
 def test_suggest_no_match_is_empty_not_failure(self):
  class Reply:
   text='v_hint="N";'
   def raise_for_status(self):pass
  with patch('requests.get',return_value=Reply()):
   self.assertEqual(security_search.suggest('不存在公司XYZ'),[])

class DisplayNameCacheTests(unittest.TestCase):
    def setUp(self): security_search.reset_cache()
    def tearDown(self): security_search.reset_cache()
    def test_exact_public_lookup_is_cached_but_never_creates_confirmation(self):
        from unittest.mock import patch
        with patch.object(security_search,'suggest',return_value=[{'code':'000001','name':'合成目录银行'}]) as suggest:
            first=security_search.search('000001',now=1000)
            second=security_search.search('000001',now=1001)
        self.assertEqual(suggest.call_count,1)
        self.assertEqual(first['status'],'ok')
        self.assertEqual(second['candidates'][0]['entity_id'],'SEC:CN:A:000001')
        self.assertTrue(first['requires_confirmation'])
        self.assertEqual(security_search.cached_name('000001',now=1001)['name'],'合成目录银行')
        self.assertIsNone(security_search.cached_name('000001',now=5000))
    def test_other_code_never_fills_requested_stock_name(self):
        from unittest.mock import patch
        with patch.object(security_search,'suggest',return_value=[{'code':'600519','name':'其他证券'}]):
            result=security_search.search('000001',now=1000)
        self.assertEqual(result['status'],'empty')
        self.assertIsNone(security_search.cached_name('000001',now=1001))
    def test_name_projection_never_waits_for_catalog_network_lock(self):
        import time
        security_search._lock.acquire()
        try:
            start=time.monotonic()
            self.assertIsNone(security_search.cached_name('000001'))
            self.assertLess(time.monotonic()-start,0.05)
        finally:security_search._lock.release()
