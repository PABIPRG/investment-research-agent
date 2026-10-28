import tempfile
import unittest
from huohuo.contracts import Invalid,canonical
from huohuo.research_entities.toolbox.context import ToolUnavailable
from test_industry_chain_fixtures import Fixture,overlay

class IndustryInheritanceTest(unittest.TestCase):
    def test_citation_must_match_actual_page_and_is_rechecked_on_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            f=Fixture(directory);f.install();f.evidence()
            body=overlay();body['companies'][0]['source_locations'][0]['page']=2
            with self.assertRaises(Invalid):f.preview('overlay',body)
            body=overlay();body['companies'][0]['source_locations'][0]['quote']='从未披露的关系'
            with self.assertRaises(Invalid):f.preview('overlay',body)
            p=f.preview('overlay',overlay())
            f.evidence(status='error')
            result=f.commit(p)
            self.assertEqual(result['status'],'failed')
            self.assertEqual(f.service.status('p')['overlay_companies'],0)
    def test_base_profiles_survive_missing_seed_but_relationship_paths_are_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            f=Fixture(directory)
            doc={'universe':[{'code':'600001','name':'合成基础公司','industry':'测试行业','market_cap':None}],
                 'universe_source':{'url':'synthetic:universe'}}
            with f.repo.connection(True) as db:db.execute('INSERT INTO industry_chain_state VALUES(?,?,?)',('p',1,canonical(doc)))
            self.assertFalse(f.service.status('p')['available'])
            self.assertTrue(f.service.status('p')['basic_available'])
            result=f.service.query('p','/graph/entity/600001')
            self.assertEqual(result['name'],'合成基础公司')
            self.assertFalse(result['provenance']['relationships_available'])
            self.assertEqual(f.service.query('p','/companies',{'keyword':'600001'})['items'][0]['code'],'600001')
            with self.assertRaises(ToolUnavailable):f.service.query('p','/graph/chain/600001')
            with self.assertRaises(ToolUnavailable):f.service.query('other','/graph/entity/600001')
    def test_quote_or_metadata_success_is_not_report_body_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            f=Fixture(directory);f.install();f.evidence()
            for tool_id,result in [('stock_quote_lookup',{'status':'ok','records':[{'price':10}]}),
                                   ('research_report_lookup',{'status':'ok','data':{'records':[{'报告名称':'供应链研究'}]}})]:
                with f.repo.connection(True) as db:db.execute('UPDATE research_tool_calls SET tool_id=?,result=? WHERE id=?',(tool_id,canonical(result),'ev1'))
                with self.subTest(tool=tool_id),self.assertRaises(Invalid):f.preview('overlay',overlay())
