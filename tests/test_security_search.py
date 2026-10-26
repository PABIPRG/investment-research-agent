import unittest
from unittest.mock import patch
from huohuo.research_entities.security_search import search, reset_cache
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
  r=search('科士达',fail,now=4000)
  self.assertEqual(r['status'],'stale');self.assertTrue(r['candidates']);self.assertFalse(r['usable_for_confirmation'])
 def test_fallback_uses_real_source_and_does_not_cache_partial_directory(self):
  with patch('huohuo.research_entities.security_search.load_catalog',side_effect=TimeoutError()), patch('huohuo.research_entities.security_search.suggest',return_value=ROWS[:1]):
   r=search('科士达')
   self.assertEqual(r['status'],'ok');self.assertEqual(r['source']['provider'],'东方财富证券搜索')
  self.assertEqual(search('茅台',lambda:ROWS)['candidates'][0]['code'],'600519')
 def test_bad_query(self):
  for q in ['',None,'x'*101]:
   with self.assertRaises(Invalid):search(q,lambda:ROWS)
