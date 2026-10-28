"""供 HTTP 与 Tool 共用的确定性白名单查询。"""
import math
from copy import deepcopy
from urllib.parse import unquote
from ..contracts import Invalid
from ..research_entities.toolbox.context import ToolUnavailable

ROUTES = {
    'status': '/data/status', 'stats': '/stats', 'companies': '/companies',
    'company': '/companies/{code}', 'entity': '/graph/entity/{key}',
    'single': '/graph/single/{code}', 'chain': '/graph/chain/{code}', 'network': '/graph/network',
}


def bounded(value, default, low, high, integer=False):
    if value is None:
        return default
    if isinstance(value, bool):
        raise Invalid('查询参数不能是布尔值')
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise Invalid('查询参数不是有效数字') from None
    if not math.isfinite(result) or not low <= result <= high or (integer and result != int(result)):
        raise Invalid('查询参数超出允许范围')
    return int(result) if integer else result


def boolean(value):
    if value in (True, 'true', '1', 1):
        return True
    if value in (False, 'false', '0', 0, None):
        return False
    raise Invalid('查询开关无效')


def query(service, principal, path, params=None):
    params = params or {}
    if not isinstance(path, str) or not isinstance(params, dict):
        raise Invalid('产业链查询格式无效')
    if path == '/data/status':
        return service.status(principal)
    with service.lock:
        state = service.seed.status()
        if not state['available']:
            raise ToolUnavailable('产业链数据尚未就绪；请到设置 → 资料源确认下载，完成后重试')
        revision, document = service.document(principal)
        service.graph.configure((principal, revision, state['generation']), document)
        graph = service.graph
        if path == '/stats':
            allowed, result = set(), graph.stats_view()
        elif path == '/companies':
            allowed = {'keyword', 'limit'}
            keyword = params.get('keyword', '')
            if not isinstance(keyword, str) or len(keyword) > 100:
                raise Invalid('公司搜索词过长或格式无效')
            result = {'items': graph.search_companies(keyword, bounded(params.get('limit'), 20, 1, 100, True))}
        elif path == '/graph/network':
            allowed = {'min_degree', 'min_market_cap', 'min_share', 'subject_only', 'include_universe'}
            if boolean(params.get('include_universe')) and not document.get('universe'):
                raise ToolUnavailable('尚未刷新 A 股基础清单；请在资料源设置中确认刷新，不应把缺少清单解释为没有公司')
            result = graph.graph_network(bounded(params.get('min_degree'), 3, 0, 10000, True), bounded(params.get('min_market_cap'), 0, 0, 1e16),
                bounded(params.get('min_share'), 10, 0, 100), boolean(params.get('subject_only')), boolean(params.get('include_universe')))
        else:
            route = next((prefix for prefix in ('/companies/', '/graph/entity/', '/graph/single/', '/graph/chain/') if path.startswith(prefix)), None)
            if route is None:
                raise Invalid('不支持的产业链查询路径')
            key = unquote(path[len(route):])
            if not key or len(key) > 100 or '/' in key or any(ord(c) < 32 for c in key):
                raise Invalid('产业链对象无效')
            allowed = {'depth_up', 'depth_down', 'top_up', 'top_down'} if route == '/graph/chain/' else set()
            if route == '/graph/chain/':
                result = graph.graph_chain(key, **{k: bounded(params.get(k), default, 0 if k.startswith('depth') else 1, maximum, True) for k, default, maximum in (('depth_up', 2, 5), ('depth_down', 2, 5), ('top_up', 3, 10), ('top_down', 2, 10))})
            else:
                function = {'/companies/': graph.company_profile, '/graph/entity/': graph.entity_profile, '/graph/single/': graph.graph_single}[route]
                result = function(key)
            if result is None:
                raise ToolUnavailable('当前图谱未覆盖此对象；可核对名称或查询关系档案，不代表不存在供应链关系')
        if set(params) - allowed:
            raise Invalid('不支持的产业链查询参数')
        return {**deepcopy(result), 'provenance': {'source': state['source'], 'downloaded_at': state['downloaded_at'], 'generation': state['generation'],
            'overlay_revision': revision, 'universe_source': document.get('universe_source'), 'disclosure': '关系可能来自披露抽取、默认展示权重或算法推断；share_source 标识其性质，默认值不是披露比例。'}}
