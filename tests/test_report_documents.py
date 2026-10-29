import io
import unittest
from pypdf import PdfWriter
from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject
import pandas as pd
from huohuo.research_entities.report_documents import fetch,download,parse_pdf
from huohuo.research_entities.toolbox.context import ToolUnavailable

RID='AP202610280000001234'
URL=f'https://pdf.dfcfw.com/pdf/H3_{RID}_1.pdf'
def pdf(text='600001 supplier relationship'):
    writer=PdfWriter();page=writer.add_blank_page(width=400,height=500)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(f'BT /F1 12 Tf 20 450 Td ({text}) Tj ET'.encode())
    page[NameObject('/Contents')]=writer._add_object(stream)
    out=io.BytesIO();writer.write(out);return out.getvalue()
class Response:
    def __init__(self,body,status=200,declared=None):self.body,self.status_code=body,status;self.headers={'Content-Length':str(len(body) if declared is None else declared)}
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def iter_content(self,size):yield self.body

class ReportDocumentsTest(unittest.TestCase):
    def test_list_selected_bounded_real_parser_returns_page_and_checksum(self):
        raw=pdf();calls=[]
        def get(url,**kwargs):calls.append((url,kwargs));return Response(raw)
        metadata=lambda:pd.DataFrame([{'股票代码':'600001','报告PDF链接':URL,'报告名称':'Synthetic report','日期':'2026-10-28'}])
        value=fetch('600001',RID,1,3,metadata,get)
        self.assertEqual(value['document_role'],'report_body')
        self.assertEqual(value['security_code'],'600001')
        self.assertIn('supplier relationship',value['pages'][0]['text'])
        self.assertEqual(value['pages'][0]['page'],1)
        self.assertEqual(len(value['document_sha256']),64)
        self.assertFalse(calls[0][1]['allow_redirects'])
        with self.assertRaises(ToolUnavailable):fetch('600002',RID,1,3,metadata,get)
        self.assertEqual(len(calls),1)
    def test_arbitrary_urls_redirects_size_and_non_pdf_are_unavailable(self):
        for url in ('http://127.0.0.1:1/x','https://user:secret@pdf.dfcfw.com/pdf/H3_'+RID+'_1.pdf',URL+'?next=private'):
            with self.assertRaises(ToolUnavailable):download(url,lambda *_a,**_k:self.fail('must not connect'))
        for response in (Response(b'not pdf'),Response(pdf(),302),Response(pdf(),declared=11*1024*1024)):
            with self.assertRaises(ToolUnavailable):download(URL,lambda *_a,**_k:response)
    def test_blank_pdf_missing_pages_and_invalid_limits_not_body_evidence(self):
        writer=PdfWriter();writer.add_blank_page(100,100);out=io.BytesIO();writer.write(out)
        for raw,start,count in [(out.getvalue(),1,1),(pdf(),2,1),(pdf(),1,6),(pdf(),True,1),(b'broken',1,1)]:
            with self.subTest(start=start,count=count),self.assertRaises(ToolUnavailable):parse_pdf(raw,start,count)
