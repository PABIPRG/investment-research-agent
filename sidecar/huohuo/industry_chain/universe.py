"""旧产业链查询算法迁入；缓存和数据目录由 Repository 实例提供。"""
import math
import re
import zlib
from copy import deepcopy
from .repository_base import memoized

_SUFFIX_RE = re.compile(r"\.(?:SZ|SH|BJ|XSHE|XSHG)$", re.I)

class Universe:

    @memoized
    def _universe_name_index(self) -> dict:
        """universe name → [code]（重名时列表 len=2，用于判定 name 匹配是否唯一）。"""
        idx: dict[str, list[str]] = {}
        for code, rec in self.universe_index().items():
            n = rec.get('name')
            if n:
                idx.setdefault(n, []).append(code)
        return idx

    def _norm_a_code(self, v) -> str:
        """归一化 6/8 位 A 股代码（去掉 .SZ/.SH/.BJ 等交易所后缀）。"""
        if isinstance(v, str):
            return _SUFFIX_RE.sub('', v).strip()
        return v

    def _resolve_a_share(self, ent: dict) -> str | None:
        """供应商/客户实体 → A 股 code。

    优先级：① id 归一化后精确命中 universe code → ② name 本身是 code
    → ③ name 唯一命中 universe（重名歧义返回 None）。全 A 股只认 A 股。
    """
        u = self.universe_index()
        if ent.get('id'):
            c = self._norm_a_code(str(ent['id']))
            if c in u:
                return c
        nm = ent.get('name')
        if not nm:
            return None
        if nm in u:
            return nm
        cand = self._universe_name_index().get(nm) or []
        if len(cand) == 1:
            return cand[0]
        return None

    def _merge_edge(self, agg: dict, src: str, tgt: str, kind: str, share, type_: str, item: str, confidence=None) -> None:
        """(src,tgt) 有向 pair 去重聚合；share / confidence 取 max（前端线宽/置信度），item 聚合。"""
        weight = self._relation_weight({'share': share, 'type': type_}, 20 if kind == 'supplier' else 10)
        share = weight['share']
        share_source = weight['share_source']
        e = agg.get((src, tgt))
        if e is None:
            agg[src, tgt] = {'kind': kind, 'share': share, 'type': type_, 'item': item or '', 'count': 1, 'confidence': confidence, 'share_source': share_source}
            return
        provenance_rank = {'inferred': 0, 'default': 1, 'disclosed': 2}
        incoming_rank = provenance_rank.get(share_source, -1)
        existing_rank = provenance_rank.get(e.get('share_source'), -1)
        if incoming_rank > existing_rank or (incoming_rank == existing_rank and share is not None and (e['share'] is None or share > e['share'])):
            e['share'] = share
            e['share_source'] = share_source
            e['type'] = type_
        if confidence is not None and (e['confidence'] is None or confidence > e['confidence']):
            e['confidence'] = confidence
        if item and item not in e['item']:
            e['item'] = e['item'] + '、' + item if e['item'] else item
        e['count'] += 1

    @memoized
    def a_share_links(self) -> dict:
        """全 A 股「A→A」供应链有向边（view-data-all + 研报 overlay + LLM 挖掘边，pair 去重）。

    返回 {"links":[{source,target,kind,type,share,item,count,confidence}],
          "degrees":{code:{"up":n,"down":n}}}   # up=供应商数(入), down=客户数(出)
    """
        u = self.universe_index()
        records: list[dict] = []
        seen: set[str] = set()
        for c in self.view_companies().values():
            cc = c.get('code') or c.get('id')
            if not cc or cc in seen:
                continue
            seen.add(cc)
            records.append(c)
        for code, extra in self._overlay().items():
            if code not in seen and code in u:
                records.append({'code': code, 'name': u[code]['name'], 'materials': extra.get('materials') or [], 'products': extra.get('products') or []})
        agg: dict[tuple, dict] = {}
        for c in records:
            c0 = c.get('code') or c.get('id')
            if c0 not in u:
                continue
            for m in c.get('materials') or []:
                for s in m.get('suppliers') or []:
                    cc = self._resolve_a_share(s)
                    if cc and cc != c0:
                        self._merge_edge(agg, cc, c0, 'supplier', s.get('share'), s.get('type') or 'direct', m.get('name'))
            for p in c.get('products') or []:
                for cu in p.get('customers') or []:
                    cc = self._resolve_a_share(cu)
                    if cc and cc != c0:
                        self._merge_edge(agg, c0, cc, 'customer', cu.get('share'), cu.get('type') or 'direct', p.get('name'))
        for l in self._llm_links():
            src, tgt = (l.get('source'), l.get('target'))
            if not src or not tgt or src == tgt or (src not in u) or (tgt not in u):
                continue
            self._merge_edge(agg, src, tgt, l.get('kind') or 'supplier', None, 'inferred', l.get('item') or '', l.get('confidence'))
        links: list[dict] = []
        degrees: dict[str, dict] = {}
        for (src, tgt), e in agg.items():
            links.append({'source': src, 'target': tgt, 'kind': e['kind'], 'type': e['type'], 'share': e['share'], 'share_source': e['share_source'], 'item': e['item'], 'count': e['count'], 'confidence': e.get('confidence')})
            degrees.setdefault(src, {'up': 0, 'down': 0})
            degrees.setdefault(tgt, {'up': 0, 'down': 0})
            degrees[src]['down'] += 1
            degrees[tgt]['up'] += 1
        return {'links': links, 'degrees': degrees}

    def _industry_color(self, ind: str) -> str:
        """行业 → 稳定色相（zlib.crc32 而非内置 hash()，后者受 PYTHONHASHSEED 影响）。"""
        if not ind:
            return '#8b97ad'
        return f"hsl({zlib.crc32(ind.encode('utf-8')) % 360} 55% 45%)"

    @memoized
    def _universe_layout(self) -> dict:
        """无 network 坐标的 A 股按行业簇布局：组内网格 + 组间 shelf 装箱 → [50,2350]×[50,1550]。

    与 network 节点映射后的 init_x/init_y 同空间（前端全 A 股模式直接用，不再二次归一化）。
    """
        u = self.universe_index()
        groups: dict[str, list[str]] = {}
        for code, rec in u.items():
            groups.setdefault(rec.get('industry') or '其他', []).append(code)
        items = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
        S, node_r, GAP, MAXW = (14, 5, 30, 2300)
        rows: list[list[tuple]] = []
        cur: list[tuple] = []
        cur_w = cur_h = y = 0
        for ind, codes in items:
            n = len(codes)
            cols = math.ceil(math.sqrt(n))
            rws = math.ceil(n / cols)
            w = (cols - 1) * S + 2 * node_r
            h = (rws - 1) * S + 2 * node_r
            if cur and cur_w + w + GAP > MAXW:
                rows.append(cur)
                y += cur_h + GAP
                cur, cur_w, cur_h = ([], 0, 0)
            cur.append((ind, codes, cols, w, h))
            cur_w += w + GAP
            cur_h = max(cur_h, h)
        if cur:
            rows.append(cur)
        out: dict[str, dict] = {}
        yy = 0.0
        for row in rows:
            row_h = max((r[4] for r in row))
            xx = 0.0
            for _ind, codes, cols, w, _h in row:
                for i, code in enumerate(codes):
                    out[code] = {'x': xx + i % cols * S + node_r, 'y': yy + i // cols * S + node_r}
                xx += w + GAP
            yy += row_h + GAP
        if not out:
            return {}
        xs = [p['x'] for p in out.values()]
        ys = [p['y'] for p in out.values()]
        bw, bh = (max(xs) - min(xs) or 1, max(ys) - min(ys) or 1)
        scale = min(2300 / bw, 1500 / bh)
        offx = 50 + (2300 - bw * scale) / 2 - min(xs) * scale
        offy = 50 + (1500 - bh * scale) / 2 - min(ys) * scale
        return {c: {'x': round(p['x'] * scale + offx, 1), 'y': round(p['y'] * scale + offy, 1)} for c, p in out.items()}
