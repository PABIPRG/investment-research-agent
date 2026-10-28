"""回测与持续影子计算；交易日对齐，失败不伪造现金收益。"""
from datetime import date,timedelta
from ..research_entities.toolbox.context import ToolUnavailable
from .history import collect
from .legacy import strategies as calc, shadow, backtest_engine, regime
from .legacy.runtime import settings

MODEL_NOTE='研究模拟：真实/受控行情、虚拟资金；仅做多、允许分数股，不含费用、滑点与涨跌停成交约束，不等于实际可成交收益。'

def backtest(strategy,payload,provider,clock):
    ins,outs,per,inside,outside,evidence={},{},{},[],[],[]
    for code in strategy['symbols']:
        rows,ev=collect(provider,code,payload['start_date'],payload['end_date'],clock)
        evidence.append(ev)
        if len(rows)<40:raise ToolUnavailable('历史日线不足 40 根，未形成回测结论')
        df=calc._make_df(rows);sig=calc.signal_series(df,strategy['kind'],strategy['params'])
        di,si,do,so=calc.split_in_out(df,sig,.3)
        ti,to=calc.simulate_trades(di,si),calc.simulate_trades(do,so)
        inside+=calc.trades_to_decision_rows(ti,code,strategy['direction'])
        outside+=calc.trades_to_decision_rows(to,code,strategy['direction'])
        ins[code]=(di,si);outs[code]=(do,so)
        a,b=calc._symbol_trade_stats(ti),calc._symbol_trade_stats(to)
        per[code]={'in_winrate_pct':a['win_rate_pct'],'in_trades':a['trades'],'in_cum_ret_pct':a['cum_ret_pct'],
                   'out_winrate_pct':b['win_rate_pct'],'out_trades':b['trades'],'out_cum_ret_pct':b['cum_ret_pct'],
                   'oos_ok':bool(b['trades']>=1 and b['win_rate_pct'] is not None and b['win_rate_pct']>=50)}
    ci=calc.portfolio_equity_curve(ins,settings.shadow_initial_capital/len(ins))
    co=calc.portfolio_equity_curve(outs,settings.shadow_initial_capital/len(outs))
    si=backtest_engine.compute_summary(inside,engine_version='strategy-date-aligned-v1')
    so=backtest_engine.compute_summary(outside,engine_version='strategy-date-aligned-v1')
    si['portfolio']=calc.curve_stats(ci);so['portfolio']=calc.curve_stats(co)
    verification,passed,reason=calc._verification_outcome(so,4)
    return {'in_sample':si,'out_of_sample':so,'thresholds_pass':passed,'verification_status':verification,
       'reason':reason,'symbol_errors':{},'model_note':MODEL_NOTE,
       'extended_backtest':{'engine_version':'strategy-date-aligned-v1','per_symbol':per,
          'oos_ok_ratio_pct':round(100*sum(p['oos_ok'] for p in per.values())/len(per),1),
          'equity_curve':{'in':calc._trim_curve(ci,400),'out':calc._trim_curve(co,400)}}},evidence

def shadow_result(strategy,docs,provider,today,clock):
    start=(today-timedelta(days=1095)).isoformat();end=today.isoformat()
    frames={};evidence=[]
    for code in strategy['symbols']:
        rows,ev=collect(provider,code,start,end,clock)
        if len(rows)<40:raise ToolUnavailable('影子验证需要至少 40 根历史日线用于指标预热')
        evidence.append(ev);frames[code]=calc._make_df(rows)
    # No mixed-as-of aggregate: a missing or stale symbol must not look like flat cash profit.
    days={str(df['date'].iloc[-1]) for df in frames.values()}
    if len(days)!=1:raise ToolUnavailable('各证券行情截止日期不一致，未写入混合日期净值')
    day=days.pop()
    if (today-date.fromisoformat(day)).days>5:raise ToolUnavailable('最新日线超过 5 个自然日，未作为当前影子证据')
    meta=docs.get('shadows','meta:'+strategy['id']) or {'track_from':day,'initial_capital':settings.shadow_initial_capital}
    if meta['track_from']<start:raise ToolUnavailable('影子跟踪起点超过本版有界重放窗口，需要先迁移完整记录')
    if day<meta['track_from']:raise ToolUnavailable('行情早于影子跟踪起点')
    updates=[];closed=[];symbols={};capital=meta['initial_capital']/len(frames)
    for code,df in frames.items():
        sig=calc.signal_series(df,strategy['kind'],strategy['params']);mask=df['date'].astype(str)>=meta['track_from']
        part=df[mask].reset_index(drop=True);signal=sig[mask].reset_index(drop=True)
        st=shadow._replay_pos(part,signal,capital,code);closed+=st['closed'];symbols[code]=st
        updates.append(('shadows',f'pos:{strategy["id"]}:{code}',st))
    nav=sum(s['equity'] for s in symbols.values())/meta['initial_capital']
    result={'name':strategy['name'],'kind':strategy['kind'],'symbols':strategy['symbols'],
       'initial_capital':meta['initial_capital'],'equity':round(nav*meta['initial_capital'],4),'nav':round(nav,6),
       'per_symbol':symbols,'symbol_errors':{},'closed_count':len(closed),'track_from':meta['track_from']}
    updates += [('shadows','meta:'+strategy['id'],meta),('shadows','trades:'+strategy['id'],
        shadow._merge_closed_trades(closed,docs.get('shadows','trades:'+strategy['id'])))]
    return day,result,updates,evidence
