"""投资台账的代码格式与单位；不把用户录入声称为交易所目录核验。"""
import json
import re
from functools import lru_cache
from pathlib import Path
from ..contracts import Invalid

@lru_cache(maxsize=1)
def known_funds():
    raw=json.loads((Path(__file__).parents[1]/'research_entities/resources/gazetteers.json').read_text())
    # 与已有研究目录复用身份；资源包含多类实体，按字段而非数组位置选择。
    result={}
    def walk(value):
        if isinstance(value,dict):
            code=value.get('identifiers',{}).get('fund_code')
            if code and value.get('entity_type_code')=='ENTITY_01_02':result[code]=value['entity_id']
            for v in value.values():walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    walk(raw)
    return result

def instrument(code):
    if not isinstance(code,str):raise Invalid('请填写六位沪深股票或场内基金代码')
    if re.fullmatch(r'(600|601|603|605|688|689|000|001|002|003|300|301)\d{3}',code):
        return {'entity_id':'SEC:CN:A:'+code,'asset_type':'stock','exchange':'SSE' if code.startswith('6') else 'SZSE','quantity_unit':'股'}
    # 支持既有目录使用的沪深场内基金代码族；格式合法不代表证券已存在。
    if re.fullmatch(r'(5[01268]\d{4}|15[9]\d{3})',code):
        return {'entity_id':known_funds().get(code,'FUND:CN:'+code),'asset_type':'fund','exchange':'SSE' if code.startswith('5') else 'SZSE','quantity_unit':'份'}
    raise Invalid('暂仅支持六位沪深 A 股及场内基金代码；请核对具体证券')

def identity(code):return instrument(code)['entity_id']
def annotate(row):return {**row,**instrument(row['ticker'])}
