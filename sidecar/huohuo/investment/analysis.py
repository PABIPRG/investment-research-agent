"""正式持仓事实的成本集中度投影；不访问旧账户、行情或另存状态。

承接旧 toolbox.local.portfolio_risk_analysis 的数量×成本与权重规则，
但未知成本时不把已知部分归一化成完整组合，不把成本权重称为实时市值权重。
"""


def cost_analysis(holdings, recorded):
    positions = []
    known = 0.0
    missing = 0
    for row in holdings:
        cost = row.get('cost_price')
        value = row['quantity'] * cost if cost is not None else None
        if value is None:
            missing += 1
        else:
            known += value
        positions.append({'code': row['ticker'], 'name': row.get('name') or row['ticker'],
                          'quantity': row['quantity'], 'cost_price': cost,
                          'cost_value': round(value, 2) if value is not None else None,
                          'cost_weight': None})
    complete = recorded and missing == 0
    if complete and known > 0:
        for item in positions:
            item['cost_weight'] = round(item['cost_value'] / known * 100, 4)
    positions.sort(key=lambda item: item['cost_weight'] if item['cost_weight'] is not None else -1,
                   reverse=True)
    return {'status': 'not_recorded' if not recorded else 'incomplete' if missing else 'ready' if positions else 'empty',
            'positions': positions, 'known_cost_subtotal': round(known, 2),
            'total_cost_value': round(known, 2) if complete else None,
            'missing_cost_positions': missing,
            'top_position_cost_weight': positions[0]['cost_weight'] if positions else None,
            'is_market_value': False,
            'note': '按已记录数量与单位成本计算，不含现金，不是实时市值或收益。'
                    + ('部分成本未知，组合总成本与完整权重保持未知。' if missing else '')}
