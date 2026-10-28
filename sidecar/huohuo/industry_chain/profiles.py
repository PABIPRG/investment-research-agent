"""旧产业链查询算法迁入；缓存和数据目录由 Repository 实例提供。"""
import math
import re
import zlib
from copy import deepcopy
from .repository_base import memoized

_SUFFIX_RE = re.compile(r"\.(?:SZ|SH|BJ|XSHE|XSHG)$", re.I)

class Profiles:

    def companies(self) -> list:
        return self._load('companies.json')

    @memoized
    def _overlay(self) -> dict:
        """研报 overlay 增量（data/reports/overlay.json）。运行期不变，重启后生效。"""
        return self.load_overlay()

    def _merge_named(self, lst: list, item: dict, child_key: str) -> None:
        """按 name 把 overlay 条目合并进列表（同名则 child_key 子项按 name 去重追加）。"""
        exist = next((x for x in lst if x.get('name') == item.get('name')), None)
        if exist is None:
            lst.append(deepcopy(item))
            return
        have = [c.get('name') for c in exist.get(child_key) or []]
        for c in item.get(child_key) or []:
            if c.get('name') and c['name'] not in have:
                exist.setdefault(child_key, []).append(deepcopy(c))
                have.append(c['name'])

    def _apply_overlay(self, rec: dict, extra: dict) -> dict:
        """单公司记录叠加 overlay 增量（materials/products 合并 + related/metrics 字段）。"""
        materials = deepcopy(rec.get('materials') or [])
        products = deepcopy(rec.get('products') or [])
        for m in extra.get('materials') or []:
            if m.get('name'):
                self._merge_named(materials, m, 'suppliers')
        for p in extra.get('products') or []:
            if p.get('name'):
                self._merge_named(products, p, 'customers')
        out = dict(rec)
        out['materials'] = materials
        out['products'] = products
        if extra.get('related') is not None:
            out['related'] = extra['related']
        if extra.get('metrics') is not None:
            out['metrics'] = extra['metrics']
        return out

    @memoized
    def _view_merged(self) -> dict:
        """view-data-all 公司记录 + 研报 overlay 叠加。

    只对 overlay 命中的 code 做 record 级合并（外层浅拷贝），大文件本体不复制。
    view_companies / 各类索引（含 _external_index）都以本函数为源，研报增量自动生效。
    """
        base = self._load('view-data-all.json')['companies']
        ov = self._overlay()
        if not ov:
            return base
        merged = dict(base)
        for code, extra in ov.items():
            matched = False
            for alias, item in base.items():
                if alias == code or item.get('code') == code:
                    merged[alias] = self._apply_overlay(item, extra)
                    matched = True
            if not matched:
                u = self.universe_index().get(code, {})
                record = {'id': code, 'code': code, 'name': u.get('name'),
                          'industry': u.get('industry'), 'is_subject': False,
                          'materials': [], 'products': [], 'source': 'confirmed_report_overlay'}
                merged[code] = self._apply_overlay(record, extra)
        return merged

    def view_companies(self) -> dict:
        return self._view_merged()

    def network(self) -> dict:
        return self._load('network-data.json')

    def market_caps(self) -> dict:
        return self._load('market-caps.json')

    def stats_raw(self) -> dict:
        return self._load('stats.json')

    @memoized
    def _view_name_index(self) -> dict:
        """view_data 中 name → code（2594 实体，用于 name/供应商解析）。"""
        idx: dict[str, str] = {}
        for code, c in self.view_companies().items():
            n = c.get('name')
            if n:
                idx[n] = code
        return idx

    @memoized
    def _cap_index(self) -> dict:
        """code → market-caps.json 单条（市值/价格/展示文案）。"""
        idx: dict[str, dict] = {}
        for entry in self.market_caps().values():
            code = entry.get('code')
            if code:
                idx[code] = entry
        return idx

    def _resolve_code(self, name_or_id: str) -> str | None:
        """实体名/ID → 核心公司 code（不在图谱内的实体返回 None，BFS 视为叶子）。"""
        v = self.view_companies()
        if name_or_id in v:
            return name_or_id
        return self._view_name_index().get(name_or_id)

    def _view(self, code: str) -> dict | None:
        return self.view_companies().get(code)

    @memoized
    def _external_index(self) -> dict:
        """非核心实体 key(id/name) → {id, name, as_supplier:[], as_customer:[]}

    只聚合并跳过核心公司自身（自环）。注意 view-data-all 里同一家公司
    同时以 code 和 name 两个 key 出现，故按真实 code 去重只处理一次。
    实体只以供应商/客户身份散落在其它公司的 materials/products 记录里，
    没有独立档案；本索引用于生成「全图关系档案」。"""
        idx: dict[str, dict] = {}
        seen: set[str] = set()
        for _k, c in self.view_companies().items():
            ccode = c.get('code') or c.get('id')
            if not ccode or ccode in seen:
                continue
            seen.add(ccode)
            cname = c.get('name')
            for m in c.get('materials') or []:
                for s in m.get('suppliers') or []:
                    if s.get('name') in (cname, ccode) or s.get('id') in (cname, ccode):
                        continue
                    key = s.get('id') or s.get('name')
                    if not key:
                        continue
                    rec = idx.setdefault(key, {'id': s.get('id'), 'name': s.get('name'), 'as_supplier': [], 'as_customer': []})
                    if s.get('name') and s.get('name') != key:
                        idx.setdefault(s['name'], rec)
                    rec['as_supplier'].append({'company_code': ccode, 'company_name': cname, 'item': m.get('name'), **self._relation_weight(s, 20), 'type': s.get('type') or 'direct', 'note': s.get('note'), 'confidence': s.get('confidence')})
            for p in c.get('products') or []:
                for cu in p.get('customers') or []:
                    if cu.get('name') in (cname, ccode) or cu.get('id') in (cname, ccode):
                        continue
                    key = cu.get('id') or cu.get('name')
                    if not key:
                        continue
                    rec = idx.setdefault(key, {'id': cu.get('id'), 'name': cu.get('name'), 'as_supplier': [], 'as_customer': []})
                    if cu.get('name') and cu.get('name') != key:
                        idx.setdefault(cu['name'], rec)
                    rec['as_customer'].append({'company_code': ccode, 'company_name': cname, 'item': p.get('name'), **self._relation_weight(cu, 10), 'type': cu.get('type') or 'direct', 'note': cu.get('note'), 'confidence': cu.get('confidence')})
        return idx

    def entity_profile(self, key: str) -> dict | None:
        """通用实体档案：核心公司 → 完整档案；非核心实体 → 全图关系档案；A 股兜底 → 基础档案。

    判定顺序：图谱核心公司（code/name）→ 图谱非核心实体（key）→ 全 A 股兜底（6/8 位数字 code）。
    """
        code = self._resolve_code(key)
        if code:
            p = self.company_profile(code)
            if p:
                return p
        rec = self._external_index().get(key)
        if rec:
            ov = self._overlay().get(rec.get('id')) or {}
            return {'id': rec.get('id'), 'name': rec.get('name'), 'is_subject': False, 'appearance_count': len(rec['as_supplier']) + len(rec['as_customer']), 'as_supplier': rec['as_supplier'], 'as_customer': rec['as_customer'], 'metrics': ov.get('metrics') or [], 'related': ov.get('related') or [], 'report_materials': ov.get('materials') or [], 'report_products': ov.get('products') or []}
        if key.isdigit() and len(key) in (6, 8):
            u = self.universe_index().get(key)
            if u:
                ov = self._overlay().get(key) or {}
                return {'code': u['code'], 'name': u['name'], 'industry': u.get('industry') or '', 'market_cap': u.get('market_cap'), 'board': u.get('board'), 'is_subject': False, 'source': 'a_share_universe', 'appearance_count': 0, 'as_supplier': [], 'as_customer': [], 'metrics': ov.get('metrics') or [], 'related': ov.get('related') or [], 'note': '全 A 股基础档案：暂无关产业链数据（该股尚未被研报/图谱覆盖）'}
        return None

    def search_companies(self, keyword: str, limit: int=20) -> list[dict]:
        q = (keyword or '').strip().lower()
        out: list[dict] = []
        rows = list(self.companies())
        known = {c.get('code') for c in rows}
        for c in self.view_companies().values():
            if c.get('code') not in known:
                rows.append(c)
                known.add(c.get('code'))
        for c in self.universe_index().values():
            if c['code'] not in known:
                rows.append({**c,'is_subject':False})
                known.add(c['code'])
        for c in rows:
            name = (c.get('name') or '').lower()
            code = (c.get('code') or '').lower()
            industry = (c.get('industry') or '').lower()
            if q and q not in name and (q not in code) and (q not in industry):
                continue
            out.append({'code': c.get('code'), 'name': c.get('name'), 'industry': c.get('industry'), 'exchange': c.get('exchange'), 'is_subject': bool(c.get('is_subject'))})
            if len(out) >= limit:
                break
        return out

    def company_profile(self, code: str) -> dict | None:
        c = self._view(code)
        if not c:
            if code in self.universe_index():
                return self.entity_profile(code)
            return None
        cap = self._cap_index().get(code) or {}
        ov = self._overlay().get(code) or {}
        up = self._direct_upstream_list(code)
        down = self._direct_downstream_list(code)
        return {'id': c.get('id'), 'code': c.get('code'), 'name': c.get('name'), 'industry': c.get('industry'), 'desc': c.get('desc'), 'is_subject': bool(c.get('is_subject')), 'market_cap_cny': cap.get('market_cap_cny'), 'market_cap_display': cap.get('market_cap_display') or '', 'stock_price': cap.get('price'), 'material_count': len(c.get('materials') or []), 'product_count': len(c.get('products') or []), 'supplier_count': len(up), 'customer_count': len(down), 'related': ov.get('related') or [], 'metrics': ov.get('metrics') or [], 'sources': ov.get('sources') or []}

    def stats_view(self) -> dict:
        s = self.stats_raw()
        return {'total_nodes': s.get('total_nodes'), 'total_edges': s.get('total_edges'), 'companies': s.get('companies'), 'items': s.get('items'), 'relationships': s.get('relationships'), 'macro_communities': s.get('macro_communities'), 'subject_count': s.get('companies')}
