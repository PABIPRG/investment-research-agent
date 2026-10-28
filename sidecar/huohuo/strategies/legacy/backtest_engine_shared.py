# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
from __future__ import annotations
import math
import re
from typing import Any, Optional
BULLISH_KEYWORDS = ('买入', '加仓', '强烈买入', '增持', '建仓', 'strong buy', 'buy', 'add')
BEARISH_KEYWORDS = ('卖出', '减仓', '强烈卖出', '清仓', 'strong sell', 'sell', 'reduce')
HOLD_KEYWORDS = ('持有', '震荡观望', '洗盘观察', '持有观察', 'hold', 'range-bound watch', 'shakeout watch', 'hold and watch')
WAIT_KEYWORDS = ('观望', '等待', 'wait')
NEGATION_PATTERNS = ('not', "don't", 'do not', 'no', 'never', 'avoid', '不要', '不', '别', '勿', '没有')
NEGATION_CONNECTOR_WORDS = ('建议', '应', '应当', '宜', '先', '再', '暂', '不必', '必须', '无需')
ACTION_DIRECTION = {'买入': ('up', 'long'), '卖出': ('down', 'cash'), '持有': ('not_down', 'long'), '观望': ('flat', 'cash')}
_PRICE_PATTERNS = ('目标价[位格]?[：:]?\\s*[¥\\$]?(\\d+(?:\\.\\d+)?)', '\\*\\*目标价[位格]?\\*\\*[：:]?\\s*[¥\\$]?(\\d+(?:\\.\\d+)?)', '目标[：:]?\\s*[¥\\$]?(\\d+(?:\\.\\d+)?)', '价格[：:]?\\s*[¥\\$]?(\\d+(?:\\.\\d+)?)', '[¥\\$](\\d+(?:\\.\\d+)?)', '(\\d+(?:\\.\\d+)?)元')
