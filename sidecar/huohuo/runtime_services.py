"""实例内新增能力装配与路由；所有状态仍归本实例所有。"""
from pathlib import Path
from .contracts import Invalid
from .transfer.service import TransferService
from .transfer_http import handle as transfer_http
from .market.service import MarketData
from .market.calendar import TradingCalendar
from .research_partner.market_bridge import MarketBridge
from .industry_chain.service import IndustryChainService
from .research_entities.toolbox.context import ToolUnavailable
from .strategies.worker_http import handle as strategy_worker
from .personalization.service import Personalization
from .personalization.http import handle as personalization_http
from .research_review import ResearchReview


def install(server):
    server.research_review = ResearchReview(server.repo,server.mandates.entities,server.investment)
    server.personalization = Personalization(server.mandates.store)
    root = Path(server.config['database']).parent
    server.transfer = TransferService(server.mandates.store, server.mandates.instance)
    server.market = MarketData()
    server.calendar = TradingCalendar(root / 'market' / 'calendar.json')
    from .strategies.news_source import source
    server.strategies.event_source = source(server.market, server.repo, server.config['principal'])
    server.mandates.market = server.market
    server.mandates.service.calendar = server.calendar
    server.market_bridge = MarketBridge(server.repo, server.mandates.entities, server.market)
    server.industry_chain = IndustryChainService(root / 'industry-chain', server.repo)
    server.research_tools.industry_chain = server.industry_chain
    server.industry_chain.recovery()


def handle(handler, parts):
    if personalization_http(handler, parts): return True
    if transfer_http(handler, parts): return True
    api, principal = handler.server, handler.server.config['principal']
    if parts[0] == 'research-reviews' and handler.command == 'POST':
        handler.authorized('user')
        body=handler.body()
        if parts == ['research-reviews','run']:
            exact(body,('session_id','call_id','arguments'))
            result=api.research_review.run(principal,body['session_id'],body['call_id'],body['arguments'])
        elif parts == ['research-reviews','history']:
            result=api.research_review.history(principal,body)
        else:raise Invalid('研究建议操作无效')
        handler.reply(200,result)
        return True
    if parts[:2] == ['worker', 'strategies']:
        handler.authorized('worker')
        strategy_worker(handler, parts[1:])
        return True
    if parts == ['market', 'query'] and handler.command == 'POST':
        handler.authorized('user')
        body = handler.body()
        exact(body, ('session_id', 'call_id', 'arguments'))
        handler.reply(200, api.market_bridge.run(principal, body['session_id'], body['call_id'], body['arguments']))
        return True
    if parts[0] != 'industry-chain':
        return False
    handler.authorized('user')
    chain = api.industry_chain
    if parts == ['industry-chain'] and handler.command == 'GET':
        handler.reply(200, chain.status(principal))
        return True
    if handler.command != 'POST':
        raise Invalid('产业链操作无效')
    body = handler.body()
    if parts == ['industry-chain', 'query']:
        exact(body, ('path', 'params'))
        try: result = {'status': 'ok', 'data': chain.query(principal, body['path'], body['params'])}
        except ToolUnavailable as exc: result = {'status': 'unavailable', 'error': str(exc)}
    elif len(parts) == 2 and parts[1] in ('prepare', 'commit'):
        if not isinstance(body, dict) or 'session_id' not in body:
            raise Invalid('缺少操作会话')
        session = body.pop('session_id')
        result = getattr(chain, parts[1])(principal, session, body)
    else:
        raise Invalid('产业链操作无效')
    handler.reply(200, result)
    return True


def exact(body, keys):
    if not isinstance(body, dict) or set(body) != set(keys):
        raise Invalid('请求字段无效')
