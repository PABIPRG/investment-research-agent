RULE_NAMES={'ma_cross':'均线交叉','momentum':'动量','rsi_reversal':'RSI 反转','breakout':'通道突破','bollinger':'布林带','volume_breakout':'放量突破'}
PARAM_NAMES={'fast':'快均线天数','slow':'慢均线天数','n':'观察天数','oversold':'超卖线','overbought':'超买线','k':'标准差倍数','vol_mult':'成交量倍数'}
def rule_text(kind,params):return RULE_NAMES.get(kind,kind)+'；'+'，'.join(f"{PARAM_NAMES.get(k,k)} {v}" for k,v in params.items())

"""将程序绑定的精确动作翻译成人可核对的确认内容。"""
def action_summary(docs,actions):
    records=docs.all('strategies')
    labels={'promote':'升级','demote':'降为观察','retire':'停止参与','mutate':'产生新候选'}
    names={s['code']:s['name'] for rec in records.values() for s in rec.get('securities',[])}
    lines=[]
    for i,a in enumerate(actions,1):
        subject=records.get(a.get('sid') or a.get('parent'),{}).get('name') or a.get('name') or '新策略候选'
        text=f"{i}. {subject}：{labels.get(a['type'],a['type'])}。{a.get('reason') or a.get('name') or ''}"
        if a['type']=='mutate':
            securities='、'.join(names.get(code,'证券 '+code) for code in a.get('symbols',[]))
            text+=f" 新规则 {rule_text(a.get('kind'),a.get('params') or {})}；证券 {securities}；需要重新回测。"
        lines.append(text)
    return '\n'.join(lines)
