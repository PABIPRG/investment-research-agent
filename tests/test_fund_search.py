import unittest
from types import SimpleNamespace
import pandas as pd
from unittest.mock import patch
from huohuo.research_entities.toolbox.handlers.fund_index import fund_lookup

class FundSearchTests(unittest.TestCase):
    def test_name_filters_directory_and_metacharacters_are_literal(self):
        frame=pd.DataFrame([{'基金代码':'513130','基金简称':'合成恒生科技ETF'},{'基金代码':'510300','基金简称':'合成沪深300ETF'}])
        call=SimpleNamespace(params={'name':'恒生科技'},entities=[],ctx=SimpleNamespace(call_akshare=lambda name:frame),tool_id='fund_lookup')
        # 只替换结果封装，不替换被验证的筛选算法。
        with patch('huohuo.research_entities.toolbox.handlers.fund_index.ok',side_effect=lambda call,**kw:kw),patch('huohuo.research_entities.toolbox.handlers.fund_index.empty',side_effect=lambda call,**kw:kw):
            result=fund_lookup(call);self.assertEqual([x['基金代码'] for x in result['records']],['513130'])
            call.params={'name':'['};self.assertIn('没有匹配',fund_lookup(call)['reason'])
