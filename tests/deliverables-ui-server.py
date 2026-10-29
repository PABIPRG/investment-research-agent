"""隔离成果 UAT：使用真实 HTTP/证据入库，数据明确合成，无外部请求。"""
import runpy
from pathlib import Path
from huohuo.research_entities.toolbox.registry import HANDLERS
from huohuo.research_entities.toolbox.contracts import ToolResult


def sample(call):
    return ToolResult(tool_id=call.tool_id, status='ok', source='明确合成成果验收数据',
                      warnings=['用于受控文件验收，不代表真实行情或财务'], data={'records': [
                          {'code': '000001', 'name': '平安银行', 'price': 12.3, 'cost': None, 'rate': 0.08, 'date': '2026-10-29', 'note': '=1+1'},
                          {'code': '600519', 'name': '贵州茅台', 'price': 1400.5, 'cost': 0, 'rate': -0.01, 'date': '2026-10-28', 'note': '合成记录'},
                      ]})


HANDLERS['market_overview_lookup'] = sample
runpy.run_path(str(Path(__file__).with_name('night_research_server.py')), run_name='__main__')
