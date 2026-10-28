# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
from __future__ import annotations
__all__ = ['nav_verdict', 'percentile', 'overfit_of', 'effective_lines', 'compute_profile', 'VERDICTS']
VERDICTS = ('promote', 'demote', 'retire', 'hold')
_BASIS_INSUFFICIENT = 'insufficient'
_BASIS_NOT_RUN = 'not_run'
