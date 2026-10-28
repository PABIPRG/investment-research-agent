"""DSH 提交结构化抽取候选；程序校验边界、来源及不确定性。"""
import math
import re
from copy import deepcopy
from ..contracts import Invalid, text, canonical


def exact(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise Invalid('产业链候选字段缺失或包含不支持字段')


def sequence(value, maximum=100):
    if not isinstance(value, list) or len(value) > maximum:
        raise Invalid(f'产业链列表最多 {maximum} 项')
    return value


def code(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{6}|\d{8}', value):
        raise Invalid('必须提供明确的证券代码')
    return value


def number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise Invalid('产业链数值超出范围')
    return value


def references(value):
    sequence(value, 20)
    if not value or not all(isinstance(x, str) for x in value) or len(set(value)) != len(value):
        raise Invalid('必须引用至少一项不重复的本会话资料证据')
    return [text(x, '来源证据', 100) for x in value]

def locations(value):
    sequence(value,20)
    if not value:raise Invalid('关系候选须包含正文页码与原文定位')
    result=[]
    for loc in value:
        exact(loc,('evidence_id','page','quote'))
        text(loc['evidence_id'],'证据编号',100);text(loc['quote'],'正文定位',240)
        if type(loc['page']) is not int or not 1<=loc['page']<=400:raise Invalid('正文页码无效')
        result.append(deepcopy(loc))
    return result


def relation(value):
    exact(value, ('id', 'name', 'type', 'share', 'confidence', 'note'))
    text(value['id'], '关系对象', 100)
    text(value['name'], '关系名称', 100)
    text(value['note'], '关系依据及限制', 1000)
    if value['type'] not in ('direct', 'inferred'):
        raise Invalid('关系类型必须区分披露与推断')
    if value['share'] is not None:
        number(value['share'], 0, 100)
    if value['type'] == 'inferred' and value['share'] is not None:
        raise Invalid('推断关系不能宣称披露占比')
    if value['confidence'] is not None:
        number(value['confidence'], 0, 1)
    return deepcopy(value)


def company(value):
    exact(value, ('code', 'source_evidence_ids', 'source_locations', 'materials', 'products', 'related', 'metrics'))
    result = {'code': code(value['code']), 'source_evidence_ids': references(value['source_evidence_ids'])}
    result['source_locations']=locations(value['source_locations'])
    for group, children in (('materials', 'suppliers'), ('products', 'customers')):
        result[group] = []
        for item in sequence(value[group], 30):
            exact(item, ('name', children))
            text(item['name'], group, 100)
            result[group].append({'name': item['name'], children: [relation(x) for x in sequence(item[children], 30)]})
    result['related'] = []
    for item in sequence(value['related'], 30):
        exact(item, ('name', 'relation', 'note'), ('code',))
        for key in ('name', 'relation', 'note'):
            text(item[key], key, 1000)
        if item.get('code'):
            code(item['code'])
        result['related'].append(deepcopy(item))
    result['metrics'] = []
    for item in sequence(value['metrics'], 50):
        exact(item, ('name', 'value', 'unit', 'period', 'note'))
        for key in ('name', 'value', 'unit', 'period', 'note'):
            text(item[key], key, 1000)
        result['metrics'].append(deepcopy(item))
    return result


def validate_overlay(payload):
    exact(payload, ('companies', 'inferred_links'))
    result = {'companies': [company(x) for x in sequence(payload['companies'], 20)], 'inferred_links': []}
    seen = [x['code'] for x in result['companies']]
    if len(set(seen)) != len(seen):
        raise Invalid('同一候选不能重复提交公司')
    for item in sequence(payload['inferred_links'], 100):
        exact(item, ('source', 'target', 'kind', 'item', 'confidence', 'note', 'source_evidence_ids','source_locations'))
        code(item['source']); code(item['target'])
        item={**item,'source_locations':locations(item['source_locations'])}
        if item['source'] == item['target'] or item['kind'] not in ('supplier', 'customer'):
            raise Invalid('推断边方向或类型无效')
        text(item['item'], '产品或材料', 100)
        text(item['note'], '推断理由与限制', 1000)
        number(item['confidence'], 0, 1)
        references(item['source_evidence_ids'])
        result['inferred_links'].append(deepcopy(item))
    if not result['companies'] and not result['inferred_links']:
        raise Invalid('没有可保存的产业链增量')
    if len(canonical(result).encode()) > 512 * 1024:
        raise Invalid('产业链增量最多 512 KiB')
    return result


def apply_overlay(document, payload, sources):
    updated = deepcopy(document)
    companies = updated.setdefault('companies', {})
    for row in payload['companies']:
        item = deepcopy(row)
        item['sources'] = [sources[eid] for eid in row['source_evidence_ids']]
        for group, children in (('materials', 'suppliers'), ('products', 'customers')):
            for entry in item[group]:
                for edge in entry[children]:
                    edge['sources'] = deepcopy(item['sources'])
        companies[row['code']] = item
    existing = {(x['source'], x['target'], x['kind']): x for x in updated.get('inferred_links', [])}
    for row in payload['inferred_links']:
        row = {**row, 'sources': [sources[eid] for eid in row['source_evidence_ids']]}
        existing[(row['source'], row['target'], row['kind'])] = row
    updated['inferred_links'] = list(existing.values())
    if len(companies) > 10000 or len(existing) > 20000 or len(canonical(updated).encode()) > 32 * 1024 * 1024:
        raise Invalid('实例产业链增量达到存储上限，请先清理旧增量')
    return updated
