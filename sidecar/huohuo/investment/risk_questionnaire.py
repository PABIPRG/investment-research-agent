"""风险偏好题库与确定性计分。
题库来自旧仓 9c23b1f adapter/kyc.py（Apache-2.0，见 third-party）。
修改：分数只由题库选项索引计算，拒绝模型分数、重复、缺答及额外字段。
不调用模型，不设置仓位或通知；保存由 Investment 服务负责。
"""
from copy import deepcopy
from ..contracts import Invalid,text

TIERS = {'quick': ('horizon', 'loss_tolerance', 'goal'),
         'full': ('horizon', 'loss_tolerance', 'goal', 'income_stability', 'experience',
                  'drawdown_reaction', 'knowledge', 'product_pref')}
LABELS = {'conservative': '保守型', 'balanced': '稳健型', 'aggressive': '进取型'}


def questionnaire():
    return {tier: [{'qid': qid, 'title': BANK[qid]['title'],
                    'options': [x['label'] for x in BANK[qid]['options']]} for qid in qids]
            for tier, qids in TIERS.items()}


def score(payload):
    if not isinstance(payload, dict) or not {'tier','answers'}<=set(payload) or set(payload)-{'tier','answers','statement'}:
        raise Invalid('请选择问卷并完整回答，不接受自填分数或画像')
    tier, answers = payload['tier'], payload['answers']
    if not isinstance(tier, str) or tier not in TIERS:
        raise Invalid('问卷须为三题速测或八题完整问卷')
    qids = TIERS[tier]
    if not isinstance(answers, list) or len(answers) != len(qids):
        raise Invalid('请完成所选问卷的全部题目')
    chosen = {}
    for answer in answers:
        if not isinstance(answer, dict) or set(answer) != {'qid', 'option'}:
            raise Invalid('答案只能包含题目和所选选项')
        qid, option = answer['qid'], answer['option']
        if not isinstance(qid, str) or qid not in qids or qid in chosen:
            raise Invalid('问卷包含重复或未知题目')
        if type(option) is not int or not 0 <= option < len(BANK[qid]['options']):
            raise Invalid('请选择题库中的一个选项')
        chosen[qid] = {'qid': qid, 'option': option, **deepcopy(BANK[qid]['options'][option])}
    total = sum(x['score'] for x in chosen.values())
    maximum = 5 * len(qids)
    profile = 'conservative' if total <= round(18 * maximum / 40) else 'balanced' if total <= round(29 * maximum / 40) else 'aggressive'
    value={'tier': tier, 'answers': [chosen[q] for q in qids], 'score': total, 'max_score': maximum,
            'profile': profile, 'label': LABELS[profile], 'scoring_version': 'legacy-v1','method':'questionnaire'}
    if 'statement' in payload:value.update(statement=text(payload['statement'],'经核对的偏好描述',4000),method='text_assisted_confirmed')
    return value

BANK = {'horizon': {'qid': 'horizon',
             'title': '你计划持有这笔资金多久？',
             'options': [{'label': '3个月以内', 'score': 1},
                         {'label': '半年到1年', 'score': 2},
                         {'label': '1-3年', 'score': 3},
                         {'label': '3-5年', 'score': 4},
                         {'label': '5年以上', 'score': 5}]},
 'loss_tolerance': {'qid': 'loss_tolerance',
                    'title': '你能接受的最大亏损幅度？',
                    'options': [{'label': '不能接受亏损，保本第一', 'score': 1},
                                {'label': '5%以内', 'score': 2},
                                {'label': '10%左右', 'score': 3},
                                {'label': '20%左右', 'score': 4},
                                {'label': '30%以上也能接受', 'score': 5}]},
 'goal': {'qid': 'goal',
          'title': '你的主要投资目标是什么？',
          'options': [{'label': '本金安全，稳定跑赢存款', 'score': 1},
                      {'label': '稳健增值，跑赢通胀即可', 'score': 2},
                      {'label': '长期增值，追求市场平均回报', 'score': 3},
                      {'label': '积极增长，博取超额收益', 'score': 4},
                      {'label': '高回报优先，接受大幅波动', 'score': 5}]},
 'income_stability': {'qid': 'income_stability',
                      'title': '你的收入稳定性 / 可投资金情况？',
                      'options': [{'label': '收入不稳定，积蓄有限', 'score': 1},
                                  {'label': '收入一般，有一定积蓄', 'score': 2},
                                  {'label': '收入稳定，有应急储备', 'score': 3},
                                  {'label': '收入较高，闲钱充裕', 'score': 4},
                                  {'label': '高收入/高净值，可承受较大损失', 'score': 5}]},
 'experience': {'qid': 'experience',
                'title': '你有多少投资经验？',
                'options': [{'label': '没有经验', 'score': 1},
                            {'label': '1年以内', 'score': 2},
                            {'label': '1-3年', 'score': 3},
                            {'label': '3-5年', 'score': 4},
                            {'label': '5年以上或专业背景', 'score': 5}]},
 'drawdown_reaction': {'qid': 'drawdown_reaction',
                       'title': '持仓出现明显亏损时，你的第一反应是？',
                       'options': [{'label': '无法承受，立即止损离场', 'score': 1},
                                   {'label': '非常焦虑，考虑退出', 'score': 2},
                                   {'label': '虽有波动，但能坚持持有', 'score': 3},
                                   {'label': '视为正常波动，冷静应对', 'score': 4},
                                   {'label': '逆势加仓，视其为机会', 'score': 5}]},
 'knowledge': {'qid': 'knowledge',
               'title': '你对股票、基金的风险收益特征了解多少？',
               'options': [{'label': '完全不了解', 'score': 1},
                           {'label': '了解一些基本概念', 'score': 2},
                           {'label': '了解主要产品的风险特征', 'score': 3},
                           {'label': '较熟悉，能分析产品结构', 'score': 4},
                           {'label': '专业投资者，深入理解', 'score': 5}]},
 'product_pref': {'qid': 'product_pref',
                  'title': '你更偏好哪类投资品种？',
                  'options': [{'label': '存款/货币基金等保本产品', 'score': 1},
                              {'label': '债券/固收类为主', 'score': 2},
                              {'label': '股债混合/均衡配置', 'score': 3},
                              {'label': '股票型基金/个股为主', 'score': 4},
                              {'label': '高波动品种/杠杆/衍生品', 'score': 5}]}}
