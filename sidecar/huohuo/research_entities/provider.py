"""受限 AKShare 子进程入口；只允许固定数据源，不接受任意函数/URL。"""
import contextlib,json,sys
from ..contracts import scope as validate_scope

def main():
    scope=validate_scope(json.loads(sys.stdin.read(20000)))
    code=scope['entity_id'].split(':')[-1]
    with contextlib.redirect_stdout(sys.stderr):
        import akshare as ak
        frame=ak.stock_profile_cninfo(symbol=code) if scope['operation']=='company_profile' else ak.stock_financial_abstract(symbol=code)
    # 复用 financials_lookup 的列选取：指标与明确期间，不转换原始单位。
    if scope['operation']=='financial_summary' and frame is not None:
        wanted=[c for c in ['选项','指标',scope['period']] if c in frame.columns]
        frame=frame[wanted]
    records=json.loads(frame.head(80).to_json(orient='records',force_ascii=False)) if frame is not None else []
    print(json.dumps({'code':code,'records':records},ensure_ascii=False,allow_nan=False))
if __name__=='__main__': main()
