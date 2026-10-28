"""有时间/资源边界的 PDF 文本子进程；无模型和网络。"""
import base64
import io
import json
import sys

def extract(raw,start,count):
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(raw),strict=True)
    if reader.is_encrypted:raise ValueError('加密研报无法读取')
    total=len(reader.pages)
    if not 1<=total<=400 or not 1<=start<=total:raise ValueError('研报页数或起始页超出边界')
    pages=[];remaining=60000
    for index in range(start-1,min(total,start-1+count)):
        text=reader.pages[index].extract_text() or ''
        if text.strip():
            clipped=text[:remaining]
            pages.append({'page':index+1,'text':clipped,'truncated':len(clipped)<len(text)})
            remaining-=len(clipped)
        if remaining<=0:break
    if not pages:raise ValueError('所选页无可提取正文；可能是扫描件，未执行 OCR')
    return {'pages':pages,'total_pages':total,'complete_document':start==1 and count>=total and remaining>0}

def main():
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU,(12,12))
            resource.setrlimit(resource.RLIMIT_AS,(768*1024*1024,768*1024*1024))
        except (ImportError,ValueError,OSError):pass
        raw=json.loads(sys.stdin.buffer.read(15*1024*1024))
        pdf=base64.b64decode(raw['pdf'],validate=True)
        if len(pdf)>10*1024*1024:raise ValueError('PDF 超过读取上限')
        print(json.dumps(extract(pdf,raw['start_page'],raw['page_count']),ensure_ascii=False))
    except Exception:
        print(json.dumps({'error':'研报正文解析失败、加密、扫描件或超出读取边界；未形成正文证据'}))

if __name__=='__main__':main()
