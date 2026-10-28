"""执行已经预览的计划；所有领域写入由外层同一 SQLite 事务覆盖。"""
from ..contracts import canonical
from ..execution import digest
from ..investment.service import Investment
from ..investment.instruments import identity
from .mandates import write_mandates


def write_facts(service,principal,plan,batch,at):
    db=service.store._connect()
    old_version,before,_=Investment(service.store)._load(principal)
    after=plan['facts']
    if before==after: return {'changed':False,'version':old_version}
    version=old_version+1
    if before['default']!=after['default']:
        after['snapshots'].append({'snapshot_id':'import-'+digest([batch,principal])[:32],'source':'legacy_import','effective_at':at,
            'previous_snapshot_id':after['snapshots'][-1].get('snapshot_id') if after['snapshots'] else None,'positions':after['default']})
    encoded=canonical(after)
    db.execute('INSERT INTO investment_facts VALUES(?,?,?,?) ON CONFLICT(principal) DO UPDATE SET version=excluded.version, document=excluded.document, updated_at=excluded.updated_at',(principal,version,encoded,at))
    db.execute('INSERT INTO investment_versions VALUES(?,?,?,?)',(principal,version,encoded,at))
    db.execute('INSERT INTO investment_audit VALUES(?,?,?,?,?)',(principal,version,'legacy_import',canonical({'batch_id':batch,'selected':plan['selected'],'rules':plan['rules']}),at))
    codes=sorted({x['ticker'] for x in before['default']+after['default']+before['watchlist']+after['watchlist']})
    event_id='investment:'+digest([principal,version])
    event={'event_id':event_id,'hook_type':'investment.facts_revised','schema_version':'1','producer':'huohuo-investment','occurred_at':at,'observed_at':at,
        'subject_ids':[identity(x) for x in codes],'source_version':str(version),'content_hash':digest(after),
        'payload':{'principal_id':principal,'fact_version':version,'previous_version':old_version,'change_type':'legacy_import','feature_key':'legacy_import',
                   'changed_fields':plan['selected'],'ticker':None,'batch_id':batch}}
    db.execute('INSERT INTO investment_outbox VALUES(?,?,?,?,0)',(event_id,principal,version,canonical(event)))
    return {'changed':True,'version':version,'event_id':event_id}


def write_plan(service,principal,plan,package,batch,at):
    db=service.store._connect()
    facts=write_facts(service,principal,plan,batch,at)
    for record in plan['strategies']:
        db.execute("INSERT INTO strategy_documents VALUES(?,'strategies',?,?) ON CONFLICT(principal,collection,id) DO UPDATE SET document=excluded.document",(principal,record['id'],canonical(record)))
    write_mandates(service.store,plan['mandates'])
    archives=0
    for item in plan['archives']:
        identifier='ARCH_'+digest([principal,item['category'],item['source_id'],item['document']])[:32]
        source={'format':'legacy_product','source_digest':package['source_digest'],'source_id':item['source_id'],'readonly':True,'new_research_evidence':False,'dsh_session':False}
        cursor=db.execute('INSERT OR IGNORE INTO legacy_transfer_archives VALUES(?,?,?,?,?,?,?,?,?)',(identifier,principal,batch,item['category'],item['source_id'],item['title'],canonical(item['document']),canonical(source),at))
        archives+=cursor.rowcount
    return {'facts':facts,'strategies':len(plan['strategies']),'mandates':len(plan['mandates']),'archives_added':archives}
