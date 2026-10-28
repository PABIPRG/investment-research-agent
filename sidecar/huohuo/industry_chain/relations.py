"""旧产业链查询算法迁入；缓存和数据目录由 Repository 实例提供。"""
import math
import re
import zlib
from copy import deepcopy
from .repository_base import memoized

_SUFFIX_RE = re.compile(r"\.(?:SZ|SH|BJ|XSHE|XSHG)$", re.I)

class Relations:

    def _relation_weight(self, relation: dict, default_share: float) -> dict:
        """投影关系权重及来源；合法的 0 必须保留，推断边不伪装成占比。"""
        existing_source = relation.get('share_source')
        if existing_source == 'inferred':
            return {'share': None, 'share_source': 'inferred'}
        if existing_source in ('default', 'disclosed'):
            return {'share': relation.get('share'), 'share_source': existing_source}
        if relation.get('type') == 'inferred':
            return {'share': None, 'share_source': 'inferred'}
        share = relation.get('share')
        if isinstance(share, (int, float)) and (not isinstance(share, bool)):
            return {'share': share, 'share_source': 'disclosed'}
        return {'share': default_share, 'share_source': 'default'}

    def _merge_relation_node(self, aggregate: dict[str, dict], relation: dict, via: str | None, default_share: float) -> None:
        """按实体聚合直接关系；披露值优先于默认值，默认值优先于推断值。"""
        key = relation.get('id') or relation.get('name')
        if not key:
            return
        weight = self._relation_weight(relation, default_share)
        candidate = {'id': relation.get('id'), 'name': relation.get('name'), 'type': relation.get('type') or 'direct', **weight, 'confidence': relation.get('confidence'), 'note': relation.get('note'), 'vias': [via] if via else [], 'sources': relation.get('sources') or []}
        current = aggregate.get(key)
        if current is None:
            aggregate[key] = candidate
            return
        rank = {'inferred': 0, 'default': 1, 'disclosed': 2}
        incoming_rank = rank.get(candidate['share_source'], -1)
        current_rank = rank.get(current.get('share_source'), -1)
        if incoming_rank > current_rank or (incoming_rank == current_rank and candidate['share'] is not None and (current.get('share') is None or candidate['share'] > current['share'])):
            for field in ('share', 'share_source', 'type', 'note'):
                current[field] = candidate[field]
        confidence = candidate.get('confidence')
        if confidence is not None and (current.get('confidence') is None or confidence > current['confidence']):
            current['confidence'] = confidence
        if via and via not in current['vias']:
            current['vias'].append(via)

    def _direct_relation_rows(self, company: dict, group_key: str, relation_key: str, default_share: float) -> list[dict]:
        aggregate: dict[str, dict] = {}
        comp_name, comp_code = (company.get('name'), company.get('code'))
        for group in company.get(group_key) or []:
            via = group.get('name')
            for relation in group.get(relation_key) or []:
                if relation.get('name') in (comp_name, comp_code) or relation.get('id') in (comp_name, comp_code):
                    continue
                self._merge_relation_node(aggregate, relation, via, default_share)
        rows = []
        for node in aggregate.values():
            rows.append({**node, 'via': '、'.join(node['vias'])})
        rows.sort(key=lambda row: row['share'] or 0, reverse=True)
        return rows

    def _direct_upstream_list(self, code: str, limit: int | None=None) -> list[dict]:
        c = self._view(code)
        if not c:
            return []
        rows = self._direct_relation_rows(c, 'materials', 'suppliers', 20)
        return rows[:limit] if limit else rows

    def _direct_downstream_list(self, code: str, limit: int | None=None) -> list[dict]:
        c = self._view(code)
        if not c:
            return []
        rows = self._direct_relation_rows(c, 'products', 'customers', 10)
        return rows[:limit] if limit else rows

    def graph_single(self, code: str) -> dict | None:
        """供应商 → 原材料 → 核心公司 → 主营产品 → 下游客户（列式数据，前端画 SVG 边）。

    suppliers/customers 去重：同一实体经多材料/多产品出现时合并 via 列表。
    """
        c = self._view(code)
        if not c:
            return None
        materials = [{'id': m.get('id'), 'name': m.get('name'), 'share': m.get('share'), 'confidence': m.get('confidence')} for m in c.get('materials') or []]
        products = [{'id': p.get('id'), 'name': p.get('name'), 'share': p.get('share'), 'confidence': p.get('confidence')} for p in c.get('products') or []]
        suppliers = self._direct_relation_rows(c, 'materials', 'suppliers', 20)
        customers = self._direct_relation_rows(c, 'products', 'customers', 10)
        return {'company': self.company_profile(code), 'materials': materials, 'suppliers': suppliers, 'products': products, 'customers': customers}

    def graph_chain(self, code: str, depth_up: int=2, depth_down: int=2, top_up: int=3, top_down: int=2) -> dict | None:
        center = self.company_profile(code)
        if not center:
            return None

        def bfs(upward: bool) -> list[dict]:
            depth = depth_up if upward else depth_down
            top = top_up if upward else top_down
            fn = self._direct_upstream_list if upward else self._direct_downstream_list
            levels: list[dict] = []
            current: list[str] = [code]
            visited: set[str] = {code}
            for d in range(1, depth + 1):
                nxt: list[dict] = []
                for pid in current:
                    for node in fn(pid, top):
                        key = node.get('id') or node.get('name')
                        if key in visited:
                            continue
                        visited.add(key)
                        resolved_code = self._resolve_code(key)
                        node['code'] = resolved_code
                        node['expandable'] = bool(resolved_code)
                        node['parent_id'] = pid
                        node['depth'] = d
                        nxt.append(node)
                if not nxt:
                    break
                levels.append({'level': -d if upward else d, 'nodes': nxt})
                current = []
                for n in nxt:
                    rc = n.get('code')
                    current.append(rc if rc else n.get('name') or '')
                current = [x for x in current if x]
            return levels
        up_levels = bfs(upward=True)
        down_levels = bfs(upward=False)
        return {'center': center, 'up_levels': up_levels, 'down_levels': down_levels}
