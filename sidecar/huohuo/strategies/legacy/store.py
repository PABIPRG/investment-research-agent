# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""类型兼容面；所有实际存储均必须由当前实例注入。"""
class JsonStore:
    def __init__(self,*_args,**_kwargs):
        raise RuntimeError('策略算法必须显式注入当前实例存储')
