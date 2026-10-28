"""旧产业链查询算法迁入；缓存和数据目录由 Repository 实例提供。"""
import math
import re
import zlib
from copy import deepcopy
from .repository_base import memoized

_SUFFIX_RE = re.compile(r"\.(?:SZ|SH|BJ|XSHE|XSHG)$", re.I)

class Network:

    def _slim_node(self, n: dict) -> dict:
        keep = ('id', 'code', 'name', 'industry', 'is_subject', 'role', 'tier', 'radius', 'color', 'glowColor', 'market_cap_cny', 'badge', 'degree', 'upCount', 'downCount', 'macroId', 'macroName', 'init_x', 'init_y', 'subId', 'subName', 'scaleText', 'board', 'market_cap', 'has_view')
        return {k: n.get(k) for k in keep}

    def _graph_network_universe(self, min_share: float) -> dict:
        """全 A 股模式：全部 5901 家 A 股节点 + A→A 供应链真实边。

    忽略 min_degree / min_market_cap / subject_only（合成 A 股大多 degree=0，
    按 3 过滤会清空；外部实体不画节点故 subject_only 无意义）。min_share 仅对
    数值型 share 生效（null share 恒保留，86% 真实边无 share 数据）。
    """
        u = self.universe_index()
        net = self.network()
        al = self.a_share_links()
        uidx = self._universe_name_index()
        net_by_code: dict[str, dict] = {}
        for n in net['nodes']:
            c = n.get('code')
            if c and c in u:
                net_by_code[c] = n
                continue
            for key in (n.get('id'), n.get('name')):
                if not key:
                    continue
                cand = uidx.get(key)
                if cand and len(cand) == 1:
                    net_by_code[cand[0]] = n
                    break
        pts = [(c, n['init_x'], n['init_y']) for c, n in net_by_code.items() if isinstance(n.get('init_x'), (int, float)) and isinstance(n.get('init_y'), (int, float))]
        if pts:
            nx = [p[1] for p in pts]
            ny = [p[2] for p in pts]
            minx, maxx = (min(nx), max(nx))
            miny, maxy = (min(ny), max(ny))
            rngx, rngy = (maxx - minx or 1, maxy - miny or 1)
        else:
            minx = miny = 0.0
            rngx = rngy = 1.0
        layout = self._universe_layout()
        vc = self.view_companies()
        nodes = []
        for code, rec in u.items():
            base = {'id': code, 'code': code, 'name': rec.get('name'), 'industry': rec.get('industry') or '', 'board': rec.get('board'), 'market_cap': rec.get('market_cap'), 'market_cap_cny': rec.get('market_cap') * 100000000 if isinstance(rec.get('market_cap'), (int, float)) else None, 'has_view': code in vc}
            nn = net_by_code.get(code)
            if nn and isinstance(nn.get('init_x'), (int, float)) and isinstance(nn.get('init_y'), (int, float)):
                for k in ('radius', 'color', 'glowColor', 'macroId', 'macroName', 'subId', 'subName', 'scaleText', 'role', 'tier', 'degree', 'upCount', 'downCount'):
                    if nn.get(k) is not None:
                        base[k] = nn[k]
                base['init_x'] = round(50 + (nn['init_x'] - minx) / rngx * 2300, 1)
                base['init_y'] = round(50 + (nn['init_y'] - miny) / rngy * 1500, 1)
                base['is_subject'] = bool(nn.get('is_subject'))
            else:
                d = al['degrees'].get(code, {'up': 0, 'down': 0})
                p = layout.get(code, {'x': 50, 'y': 50})
                base.update({'is_subject': False, 'radius': 4, 'color': self._industry_color(rec.get('industry') or ''), 'degree': d['up'] + d['down'], 'upCount': d['up'], 'downCount': d['down'], 'macroId': None, 'init_x': p['x'], 'init_y': p['y']})
            nodes.append(self._slim_node(base))
        links = [l for l in al['links'] if not (min_share > 0 and l.get('share') is not None and (l['share'] < min_share))]
        return {'nodes': nodes, 'links': links, 'macro_communities': net.get('macro_communities') or [], 'stats': {'total_nodes': len(nodes), 'total_links': len(links), 'universe_mode': True, 'subject_count': sum((1 for n in nodes if n.get('is_subject'))), 'macro_communities_count': len(net.get('macro_communities') or [])}}

    def graph_network(self, min_degree: int=3, min_market_cap: float=0, min_share: float=10, subject_only: bool=False, include_universe: bool=False) -> dict:
        if include_universe:
            return self._graph_network_universe(min_share)
        net = self.network()
        raw_nodes = net['nodes']
        raw_links = net['links']
        filtered_nodes = []
        for n in raw_nodes:
            if subject_only and (not n.get('is_subject')):
                continue
            deg = n.get('degree') if n.get('degree') is not None else 0
            if deg < min_degree:
                continue
            mc = n.get('market_cap_cny')
            if min_market_cap > 0 and (mc is None or mc < min_market_cap):
                continue
            filtered_nodes.append(self._slim_node(n))
        valid = {n['id'] for n in filtered_nodes}
        filtered_links = []
        for l in raw_links:
            if l['source'] not in valid or l['target'] not in valid:
                continue
            weight = self._relation_weight(l, 20 if l.get('kind') == 'supplier' else 10)
            if min_share > 0 and weight['share'] is not None and (weight['share'] < min_share):
                continue
            filtered_links.append({'source': l['source'], 'target': l['target'], 'kind': l.get('kind'), 'type': l.get('type'), **weight, 'item': l.get('item'), 'confidence': l.get('confidence')})
        u = self.universe_index()
        macro_inds: dict[int, list[str]] = {}
        for n in raw_nodes:
            mid = n.get('macroId')
            if mid is None:
                continue
            ind = u.get(n.get('code') or '', {}).get('industry')
            if ind:
                macro_inds.setdefault(mid, []).append(ind)
        communities = []
        for cm in net.get('macro_communities') or []:
            inds = macro_inds.get(cm.get('macroId')) or []
            industry = max(set(inds), key=inds.count) if inds else None
            communities.append({'macroId': cm.get('macroId'), 'name': cm.get('name'), 'palette': cm.get('palette'), 'size': cm.get('size'), 'industry': industry})
        return {'nodes': filtered_nodes, 'links': filtered_links, 'macro_communities': communities, 'stats': net.get('stats') or {}}
