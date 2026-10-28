"""固定研报资料源：元数据选择 → 有界下载 → 隔离解析 → 正文证据。"""
import base64
import hashlib
import json
import re
import subprocess
import sys
import time
from .toolbox.context import ToolUnavailable,records_from_frame

MAX_BYTES=10*1024*1024
REPORT=re.compile(r'https://pdf\.dfcfw\.com/pdf/H3_(AP[0-9]{12,24})_1\.pdf')

def report_id(url):
    match=REPORT.fullmatch(str(url or ''))
    return match.group(1) if match else None

def download(url,get=None):
    if not REPORT.fullmatch(url):raise ToolUnavailable('研报地址不在受支持的固定公开来源中')
    import requests
    session=requests.Session();session.trust_env=False
    deadline=time.monotonic()+30
    try:
        with (get or session.get)(url,stream=True,timeout=(8,10),allow_redirects=False) as response:
            if response.status_code!=200:raise ToolUnavailable('研报下载失败或要求重定向，未读取正文')
            if int(response.headers.get('Content-Length','0'))>MAX_BYTES:raise ToolUnavailable('研报超过10MB读取上限')
            data=bytearray()
            for chunk in response.iter_content(65536):
                if time.monotonic()>deadline or len(data)+len(chunk)>MAX_BYTES:raise ToolUnavailable('研报下载超时或超过10MB读取上限')
                data.extend(chunk)
            if not data.startswith(b'%PDF-'):raise ToolUnavailable('来源没有返回 PDF 正文')
            return bytes(data)
    finally:session.close()

def parse_pdf(raw,start_page,page_count):
    if type(start_page) is not int or not 1<=start_page<=400 or type(page_count) is not int or not 1<=page_count<=5:
        raise ToolUnavailable('研报每次只能读取1至5页，起始页为1至400')
    try:
        result=subprocess.run([sys.executable,'-m','huohuo.research_entities.report_pdf_worker'],
            input=json.dumps({'pdf':base64.b64encode(raw).decode(),'start_page':start_page,'page_count':page_count}),
            text=True,capture_output=True,timeout=15,check=True)
        if len(result.stdout)>500000:raise ValueError('response too large')
        value=json.loads(result.stdout)
        if value.get('error'):raise ValueError(value['error'])
        return value
    except (ValueError,subprocess.SubprocessError):
        raise ToolUnavailable('研报正文解析失败、无可提取文字或超出读取边界；未形成正文证据') from None

def fetch(code,rid,start_page,page_count,loader,get=None):
    if not isinstance(code,str) or not re.fullmatch(r'[0-9]{6}',code) or not isinstance(rid,str) or not re.fullmatch(r'AP[0-9]{12,24}',rid):
        raise ToolUnavailable('请先查询已确认公司的研报列表并选择 report_id')
    records=records_from_frame(loader(),latest_first=False)
    selected=next((r for r in records if str(r.get('股票代码','')).zfill(6)==code and report_id(r.get('报告PDF链接'))==rid),None)
    if selected is None:raise ToolUnavailable('所选研报不在该公司当前来源列表，请刷新研报列表；未猜测或读取任意地址')
    url=selected['报告PDF链接'];raw=download(url,get)
    value=parse_pdf(raw,start_page,page_count)
    return {**value,'document_role':'report_body','security_code':code,'report_id':rid,'title':selected.get('报告名称'),
            'published_at':str(selected.get('日期') or ''),'source_url':url,'document_sha256':hashlib.sha256(raw).hexdigest()}
