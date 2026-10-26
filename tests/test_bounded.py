import unittest
from huohuo.research_entities.bounded import collect
from huohuo.contracts import scope, Invalid
S={'entity_id':'SEC:CN:A:600519','exchange':'SSE','operation':'financial_summary','period':'20260630','metric':'营业总收入','basis':'source_abstract'}
class BoundedTests(unittest.TestCase):
 def test_exact_period_and_metric(self):
  r=collect(S,lambda s:{'code':'600519','records':[{'指标':'营业总收入','20260630':123}]})
  self.assertEqual(r['status'],'ok');self.assertEqual(r['values']['unit'],'source_unspecified')
 def test_wrong_subject(self):
  self.assertEqual(collect(S,lambda s:{'code':'000001','records':[]})['status'],'error')
 def test_missing_period(self):
  self.assertEqual(collect(S,lambda s:{'code':'600519','records':[{'指标':'营业总收入','20260331':123}]})['status'],'unavailable')
 def test_unconfirmed_basis(self):
  with self.assertRaises(Invalid):scope(S|{'basis':'quarterly'})
 def test_two_entities_remain_candidates(self):
  from huohuo.research_entities.resolution import resolve
  r=resolve('600519 和 000001',{'status':'ok','rows':[{'code':'600519','name':'贵州茅台'},{'code':'000001','name':'平安银行'}],'source':{}})
  self.assertEqual(len(r['mentions']),2);self.assertTrue(r['requires_confirmation'])
 def test_unknown_name_not_invented(self):
  from huohuo.research_entities.resolution import resolve
  self.assertEqual(resolve('不明公司',{'status':'ok','rows':[],'source':{}})['candidates'],[])
