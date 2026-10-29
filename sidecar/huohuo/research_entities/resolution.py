"""组合旧实体抽取、候选检索、消歧与 Scope；目录来自既有证券搜索。"""
import re
import uuid
from . import security_search
from .extractor import Gazetteer, MentionExtractor
from .retriever import CandidateRetriever
from .disambiguator import Context, Disambiguator
from .models import EntityInstance, EntityCandidate, EntityMention
from .ports import IndexTerm
from .normalizer import normalize_text, normalize_name, qualified_security_code
from .scope_builder import ScopeBuilder
from .subjects import discussion_subjects
from .registry.intents import classify_intents, preferred_entity_types
from ..contracts import text, Invalid


def directory(query='', mention_texts=None):
    # 复用搜索模块唯一目录缓存和公共搜索回退；候选数据不接受模型自造。
    keywords=mention_texts or [query[:100] or '600519']
    rows={};sources=[];status='ok';expires=None
    for keyword in keywords:
        qualified=qualified_security_code(keyword)
        probe=security_search.search(qualified[0] if qualified else keyword)
        with security_search._lock:
            cached=list(security_search._catalog or [])
            loaded=security_search._loaded_at
        fresh=probe['source']['provider']=='AKShare stock_info_a_code_name' and probe['status'] in ('ok','empty')
        if fresh:
            return {'rows':cached,'status':'ok','source':probe['source'],'expires_at':loaded+security_search.TTL}
        sources.append(probe['source'])
        if probe['status'] not in ('ok','empty'):status='unavailable'
        if probe['status']=='ok':
            for row in probe['candidates']:
                # 搜索命中的关键词仅为候选关联，所有身份仍来自 provider。
                row=dict(row);row['aliases']=list(set(row.get('aliases',[])+[keyword]));rows[row['code']]=row
    return {'rows':list(rows.values()),'status':status,'source':{'providers':sources}}


class DirectoryRepository:
    def __init__(self, rows, discovered=()):
        self.entities = {}
        for row in rows:
            code = row['code']; name = row.get('name') or row.get('canonical_name')
            if not name: continue
            for eid, kind in [('SEC:CN:A:'+code,'ENTITY_01_01'), ('CO:CN:A:'+code,'ENTITY_02_01')]:
                self.entities[eid] = EntityInstance(entity_id=eid,entity_type_code=kind,canonical_name=name,
                    aliases=row.get('aliases',[]),identifiers={'security_code':code,'company_code':code},source='证券目录关联上市公司')
        for entry in Gazetteer().entities:
            self.entities[entry.entity_id] = EntityInstance(entity_id=entry.entity_id,entity_type_code=entry.entity_type_code,canonical_name=entry.canonical_name,aliases=list(entry.aliases),identifiers=dict(entry.identifiers),attributes=dict(entry.attributes),source='内置实体词典')
        for entity in discovered:
            self.entities[entity.entity_id] = entity
    def get(self, eid): return self.entities.get(eid)
    def find_by_identifier(self,key,value): return [e for e in self.entities.values() if e.identifiers.get(key)==value]
    def find_by_name(self,name,*,type_codes=None,limit=30):
        return [EntityCandidate(entity_id=e.entity_id,entity_type_code=e.entity_type_code,canonical_name=e.canonical_name,confidence=.95,source=e.source,match_reason=['name_match']) for e in self.entities.values() if (not type_codes or e.entity_type_code in type_codes) and normalize_name(name) in [normalize_name(n) for n in [e.canonical_name,*e.aliases]]][:limit]
    def terms(self):
        return [IndexTerm(n,e.entity_id,e.entity_type_code) for e in self.entities.values() for n in [e.canonical_name,*e.aliases]]


def resolve(query, catalog=None, prior=(), mention_texts=None):
    query=normalize_text(text(query,'query',2000)); catalog=catalog if catalog is not None else directory(query,mention_texts)
    repo=DirectoryRepository(catalog['rows'],catalog.get('discovered_entities',()));extractor=MentionExtractor()
    mentions=extractor.extract(query,extractor.build_trie(repo.terms()))
    if mention_texts is not None:
        if not isinstance(mention_texts,list) or len(mention_texts)>12:raise Invalid('提及列表无效')
        for index,raw in enumerate(mention_texts):
            raw=normalize_text(text(raw,'mention',100))
            if raw not in query:raise Invalid('提及必须来自用户原文')
            start=query.index(raw);end=start+len(raw)
            if any(m.start_offset==start and m.end_offset==end for m in mentions):continue
            # 模型可提取原文片段，但候选 ID 只能来自目录；部分名称匹配仍需用户选择。
            matches=[e for e in repo.entities.values() if any(raw.casefold() in n.casefold() for n in [e.canonical_name,*e.aliases])]
            mentions=[m for m in mentions if not(start<=m.start_offset and end>=m.end_offset)]
            mentions.append(EntityMention(mention_id='TEXT_'+str(index),raw_text=raw,normalized_text=raw,start_offset=start,end_offset=end,candidate_entity_ids=[e.entity_id for e in matches],entity_type_candidates=list({e.entity_type_code for e in matches})))
    mentions.sort(key=lambda m:m.start_offset)
    intents=classify_intents(query);context=Context([i.intent_code for i in intents],preferred_entity_types(intents),set())
    retriever=CandidateRetriever(repo);disambiguator=Disambiguator(repo)
    resolved=[]
    for m in mentions:
        local=context
        # 同一句显式区分公司和股票时，按提及后的类型词保留两个身份。
        suffix=query[m.end_offset:m.end_offset+2]
        if suffix in ('股票','证券'):
            local=Context(['QUOTE_CHECK'],['ENTITY_01_01'],context.portfolio_members)
        elif suffix=='公司':
            local=Context([],['ENTITY_02_01'],context.portfolio_members)
        resolved.append(disambiguator.resolve(m,retriever.retrieve(m),local))
    mentions=resolved
    # 单纯换名称/代码继续讨论时沿用本会话身份；明确公司/股票或新任务意图仍重新消歧。
    if all(i.intent_code=='GENERAL_RESEARCH' for i in intents) and not any(word in query for word in ('公司','股票','证券')):
        known={c['entity_id'] for c in prior}
        for m in mentions:
            matches=known & set(m.candidate_entity_ids)
            if (m.resolution_reason or '').startswith('company_security_pair:') and len(matches)==1:
                m.resolved_entity_id=next(iter(matches))
                m.resolution_reason='company_security_pair:conversation_confirmation'
    mentions=[m.model_copy(update={'candidates':[],'candidate_entity_ids':[],'resolved_entity_id':None,'resolution_status':'unresolved','resolution_reason':'候选过多，请提供更完整名称'}) if len(m.candidates)>8 else m for m in mentions]
    # 代词只引用本会话有效的结构化确认；多个对象始终保持歧义。
    unique={c['entity_id']:c for c in prior}
    for match in re.finditer(r'它们|他们|这两家|这家公司|这只股票|它|该公司|该股',query):
        if any(match.start()<m.end_offset and match.end()>m.start_offset for m in mentions):continue
        candidates=[EntityCandidate(entity_id=c['entity_id'],entity_type_code=c['entity_type_code'],canonical_name=c['label'],confidence=1,source='本会话用户确认') for c in unique.values()]
        if not candidates:continue
        mentions.append(EntityMention(mention_id='REF_'+str(match.start()),raw_text=match.group(),start_offset=match.start(),end_offset=match.end(),candidate_entity_ids=list(unique),candidates=candidates,resolution_status='resolved' if len(candidates)==1 else 'ambiguous',resolved_entity_id=next(iter(unique)) if len(candidates)==1 else None,confidence=1,resolution_reason='conversation_confirmation'))
    result=ScopeBuilder().build(request_id=str(uuid.uuid4()),raw_query=query,intents=intents,mentions=mentions,collections=[],tools=[],tool_warnings=[]).model_dump(mode='json')
    result.update(mentions=[m.model_dump(mode='json') for m in mentions],discussion_subjects=[s.model_dump(mode='json') for s in discussion_subjects(mentions,query)],confirmation_protocol='discussion_subjects_v1',provider_status=catalog['status'],source=catalog['source'],source_expires_at=catalog.get('expires_at'),requires_confirmation=True)
    result['candidates']=[c.model_dump(mode='json') for m in mentions for c in m.candidates]
    details={}
    for candidate in result['candidates']:
        eid=candidate['entity_id'];entity=repo.get(eid);previous=unique.get(eid,{})
        details[eid]={'identifiers':dict(entity.identifiers if entity else previous.get('identifiers',{})),
            'attributes':dict(entity.attributes if entity else previous.get('attributes',{})),
            'source_evidence':catalog.get('discovered_evidence',{}).get(eid) or previous.get('source_evidence')}
    result['entity_details']=details
    if not mentions:result['clarification_questions'].append('请补充完整名称或代码；当前未识别出可确认对象。')
    if catalog['status']!='ok':result['clarification_questions'].append('实体目录暂不可用，不能把数据源失败当作对象不存在；请重试。')
    return result
