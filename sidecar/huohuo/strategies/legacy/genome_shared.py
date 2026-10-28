# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
from __future__ import annotations
from typing import Any, Optional
REGIMES = ('high_vol', 'trend_up', 'trend_down', 'oscillation')
NICHE_FAMILIES: dict[str, tuple[str, ...]] = {'利空反弹': ('rsi_reversal', 'bollinger'), '利好动量': ('momentum', 'breakout')}
_KIND_TO_NICHE: dict[str, str] = {kind: niche for niche, kinds in NICHE_FAMILIES.items() for kind in kinds}
__all__ = ['REGIMES', 'regime_gate_default', 'gene_for', 'default_genome', 'read_gene', 'gate_enabled', 'regime_allowed', 'factor_family', 'pool_scope', 'NICHE_FAMILIES', 'family_of', 'family_alternatives']
