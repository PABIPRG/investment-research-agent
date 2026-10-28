# 迁移修改：拆分并适配火火侧车实例存储、配置和时钟（2026-10-28）。
# 原代码及适用许可见 third-party/dsh-trading-core-LICENSE、来源说明.md 和本目录 provenance.json。
"""本版按用户请求运行，不启动旧调度器或虚构下一次运行。"""
def next_closed_loop_run_at(): return None
