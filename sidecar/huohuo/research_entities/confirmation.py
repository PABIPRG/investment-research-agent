"""实体确认由原生问答桥写入；身份和期限由程序持有，不接受模型声明已确认。"""
import json
import uuid
from .resolution import resolve, directory as default_directory
from ..contracts import Invalid, canonical, text
from ..execution import digest

TTL=3600
class EntityConfirmation:
    def __init__(self,repo,directory=default_directory):self.repo,self.directory=repo,directory
    def context(self,principal,session):
        text(principal,'principal',200);text(session,'session',200)
    def current(self,principal,session):
        self.context(principal,session)
        with self.repo.connection() as db:
            return [json.loads(r['payload']) for r in db.execute('SELECT payload FROM entity_confirmations WHERE principal=? AND session=? AND active=1 AND expires_at>?',(principal,session,self.repo.clock()))]
    def resolve(self,principal,session,query,mention_texts=None):
        self.context(principal,session)
        text(query,'query',2000)
        if mention_texts is not None:
            if not isinstance(mention_texts,list) or len(mention_texts)>12:raise Invalid('提及列表无效')
            for mention in mention_texts:
                if text(mention,'mention',100) not in query:raise Invalid('提及必须来自用户原文')
        prior=self.current(principal,session)
        catalog=self.directory(query,mention_texts) if self.directory is default_directory else self.directory()
        from .instrument_discovery import compose
        catalog=compose(self.repo,principal,session,query,catalog,ttl=TTL)
        result=resolve(query,catalog,prior,mention_texts)
        for m in result['mentions']:
            matches=[c for c in prior if c['entity_id'] in m['candidate_entity_ids'] and (c['mention']==m['raw_text'] or (m.get('resolution_reason')=='conversation_confirmation' and len(m['candidates'])==1))]
            if len(matches)==1:m['confirmation']=matches[0]
        result['requires_confirmation']=any(not m.get('confirmation') for m in result['mentions']) or not result['mentions']
        result['inferred_scope_status']=result['status']
        if result['requires_confirmation']:result['status']='pending_clarification'
        sid=str(uuid.uuid4());version=digest(result);expires=min(self.repo.clock()+TTL,result.get('source_expires_at') or self.repo.clock()+TTL)
        expires=min([expires]+[m['confirmation']['expires_at'] for m in result['mentions'] if m.get('confirmation')])
        result.update(snapshot_id=sid,version=version,expires_at=expires)
        with self.repo.connection(True) as db:db.execute('INSERT INTO entity_snapshots VALUES(?,?,?,?,?,?)',(sid,principal,session,version,canonical(result),expires))
        return result
    def snapshot(self,principal,session,sid,version):
        self.context(principal,session)
        with self.repo.connection() as db:
            row=db.execute('SELECT * FROM entity_snapshots WHERE id=? AND principal=? AND session=?',(sid,principal,session)).fetchone()
            if not row or row['version']!=version or row['expires_at']<=self.repo.clock():raise Invalid('候选已过期或不属于当前对话，请重新查询')
            result=json.loads(row['payload'])
            if result['provider_status']!='ok':raise Invalid('目录不可用，不能确认过期候选，请重试')
            for m in result['mentions']:
                if m.get('confirmation'):
                    self.validate(principal,session,m['confirmation']['confirmation_id'],m['confirmation']['entity_id'])
            return result
    def confirm(self,principal,session,sid,version,choices,source_call):
        text(source_call,'native answer call',200)
        if not isinstance(choices,dict) or not choices:raise Invalid('尚未选择对象')
        with self.repo.connection(True) as db:
            snapshot=self.snapshot(principal,session,sid,version)
            mentions={m['mention_id']:m for m in snapshot['mentions']};selected=[]
            for mid,eid in choices.items():
                candidate=next((c for c in mentions.get(mid,{}).get('candidates',[]) if c['entity_id']==eid),None)
                if not candidate:raise Invalid('选择不属于候选版本')
                old=db.execute('SELECT * FROM entity_confirmations WHERE snapshot_id=? AND mention_id=? AND active=1',(sid,mid)).fetchone()
                if old and old['entity_id']==eid:
                    selected.append(json.loads(old['payload']));continue
                # 改选同一文字提及撤销旧确认，保留其他对象。
                raw=mentions[mid]['raw_text']
                for prior in db.execute('SELECT id,payload FROM entity_confirmations WHERE principal=? AND session=? AND active=1',(principal,session)).fetchall():
                    if json.loads(prior['payload'])['mention']==raw:db.execute('UPDATE entity_confirmations SET active=0 WHERE id=?',(prior['id'],))
                cid=str(uuid.uuid4());item={'confirmation_id':cid,'entity_id':eid,'entity_type_code':candidate['entity_type_code'],'label':candidate['canonical_name'],'mention':raw,'snapshot_id':sid,'version':version,'expires_at':snapshot['expires_at'],'source':'native_user_answer'}
                details=snapshot.get('entity_details',{}).get(eid,{})
                item.update(identifiers=details.get('identifiers',{}),attributes=details.get('attributes',{}),source_evidence=details.get('source_evidence'))
                if eid.startswith(('SEC:CN:A:','CO:CN:A:')):
                    code=eid.split(':')[-1]
                    item['execution_entity_id']='SEC:CN:A:'+code
                    item['exchange']='SSE' if code.startswith(('600','601','603','605','688','689')) else 'SZSE'
                    item['operations']=['company_profile','financial_summary','news'] if eid.startswith('CO:') else ['quote_snapshot','company_profile','financial_summary','market_quote','market_technical','news','market_brief']
                else:item['operations']=[]
                db.execute('INSERT INTO entity_confirmations VALUES(?,?,?,?,?,?,?,?,?,1)',(cid,principal,session,sid,mid,eid,canonical(item),source_call,snapshot['expires_at']))
                selected.append(item)
            return {'confirmations':selected,'mandate_created':False,'guidance':'已确认讨论对象；尚未授权或创建持续委托。'}
    def validate(self,principal,session,cid,eid,operation=None):
        self.context(principal,session)
        with self.repo.connection() as db:
            row=db.execute('SELECT * FROM entity_confirmations WHERE id=? AND principal=? AND session=? AND active=1 AND expires_at>?',(cid,principal,session,self.repo.clock())).fetchone()
            if not row:raise Invalid('缺少有效的本对话实体确认，请重新选择对象')
            item=json.loads(row['payload'])
            # 公司身份可明确映射到其已确认证券关联供受控公司研究使用。
            expected=item['entity_id']
            if expected.startswith('CO:CN:A:') and operation in ('company_profile','financial_summary','news'):
                expected=expected.replace('CO:CN:A:','SEC:CN:A:')
            if expected!=eid:raise Invalid('研究对象与用户确认不一致')
            return item
