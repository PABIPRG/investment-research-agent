"""直接市场查询复用实例数据能力与研究证据台账；不创建监控授权。"""
import json
from ..contracts import Invalid, canonical, text
from ..execution import Conflict, digest


class MarketBridge:
    def __init__(self, repo, confirmations, market):
        self.repo, self.confirmations, self.market = repo, confirmations, market

    def run(self, principal, session, call_id, arguments):
        text(session, 'session', 200)
        text(call_id, 'call_id', 200)
        if not isinstance(arguments, dict) or set(arguments) - {
            'operation', 'confirmation_id', 'kind', 'limit', 'period', 'lookback', 'min_amount_yi', 'include_slow'}:
            raise Invalid('市场查询参数无效')
        operation = arguments.get('operation')
        if operation not in {'quotes', 'technical', 'news', 'brief', 'scan'}:
            raise Invalid('不支持的市场查询')
        request = {k: v for k, v in arguments.items() if k != 'confirmation_id'}
        if operation in {'quotes', 'technical', 'brief'} or arguments.get('confirmation_id'):
            confirmed = self.confirmations.validate(principal, session,
                arguments.get('confirmation_id'), self._entity(principal, session, arguments.get('confirmation_id')))
            entity = confirmed.get('execution_entity_id', confirmed['entity_id'])
            if not entity.startswith('SEC:CN:A:'):
                raise Invalid('市场查询需要已确认的沪深 A 股对象')
            code = entity.split(':')[-1]
            request['codes' if operation in {'quotes', 'brief'} else 'code'] = [code] if operation in {'quotes', 'brief'} else code
        key, fingerprint = digest([principal, session, call_id, 'query_market']), digest(arguments)
        with self.repo.connection(True) as db:
            row = db.execute('SELECT fingerprint,result FROM research_tool_calls WHERE id=?', (key,)).fetchone()
            if row:
                if row['fingerprint'] != fingerprint:
                    raise Conflict('同一调用不能改变查询范围')
                return json.loads(row['result']) if row['result'] else {'status': 'unavailable', 'error': '原查询未完成，请明确重试'}
            if db.execute('SELECT COUNT(*) FROM research_tool_calls WHERE principal=? AND session=? AND created_at>?', (principal, session, self.repo.clock()-60)).fetchone()[0] >= 20:
                raise Invalid('本会话每分钟最多 20 次资料查询')
            db.execute('INSERT INTO research_tool_calls VALUES(?,?,?,?,?,?,?,?,?)',
                (key, principal, session, call_id, 'query_market', fingerprint, canonical(arguments), None, self.repo.clock()))
        result = self.market.query(request)
        result = dict(result, evidence_id=key, monitoring_created=False)
        with self.repo.connection(True) as db:
            db.execute('UPDATE research_tool_calls SET result=? WHERE id=?', (canonical(result), key))
        return result

    def _entity(self, principal, session, cid):
        found = next((c for c in self.confirmations.current(principal, session) if c['confirmation_id'] == cid), None)
        if not found:
            raise Invalid('请先确认本次查询的证券对象')
        return found['entity_id']
