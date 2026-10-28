"""用户上传 → 分类预览 → 确认 → 同库原子导入；不恢复旧运行或授权。"""
import json
import re
import time
import uuid
from datetime import datetime,timezone
from ..contracts import Invalid,canonical,text
from ..execution import Conflict,Missing,digest
from .package import decode
from .planning import available,build_plan,state_version
from .writing import write_plan
from .changes import page


def exact(value,keys):
    if not isinstance(value,dict) or set(value)!=set(keys): raise Invalid('导入请求字段缺失或包含不支持字段')


class TransferService:
    def __init__(self,store,instance_id,*,clock=time.time,name_resolver=None):
        self.store,self.instance_id,self.clock=store,instance_id,clock
        self.resolve_name=name_resolver or (lambda _code: '')

    def stamp(self): return datetime.fromtimestamp(self.clock(),timezone.utc).isoformat()

    def upload(self,principal,session,body):
        exact(body,('request_key','filename','content'))
        text(principal,'用户',200);text(session,'会话',200);text(body['request_key'],'请求标识',200)
        filename=body['filename']
        if not isinstance(filename,str) or not re.fullmatch(r'[^/\\\x00]{1,200}\.json',filename,re.I): raise Invalid('请选择 JSON 文件；不接受文件路径')
        package=decode(body['content'])
        fingerprint=digest({'filename':filename,'source_digest':package['source_digest']})
        with self.store.transaction():
            db=self.store._connect()
            row=db.execute('SELECT * FROM legacy_transfer_uploads WHERE principal=? AND session=? AND request_key=?',(principal,session,body['request_key'])).fetchone()
            if row:
                if row['fingerprint']!=fingerprint: raise Conflict('上传请求标识已用于其他文件')
                return self.upload_view(row)
            if db.execute('SELECT count(*) FROM legacy_transfer_uploads WHERE principal=?',(principal,)).fetchone()[0]>=20: raise Invalid('已保存 20 份上传，请删除不用的预览文件后再上传')
            summary={'categories':available(package),'warnings':package['warnings'],'missing_attachments':[x['name'] for x in package['attachments']],
                'notice':'上传只保存脱敏后的候选，不修改正式业务记录；旧配置、凭据、任务队列和通知授权不会恢复。'}
            uid='UPL_'+uuid.uuid4().hex
            db.execute('INSERT INTO legacy_transfer_uploads VALUES(?,?,?,?,?,?,?,?,?)',(uid,principal,session,body['request_key'],fingerprint,filename,canonical(package),canonical(summary),self.clock()))
            return self.upload_view(db.execute('SELECT * FROM legacy_transfer_uploads WHERE id=?',(uid,)).fetchone())

    def uploads(self,principal):
        with self.store.transaction():
            rows=self.store._connect().execute('SELECT * FROM legacy_transfer_uploads WHERE principal=? ORDER BY created_at DESC,id',(principal,)).fetchall()
            return {'items':[self.upload_view(x) for x in rows]}

    @staticmethod
    def upload_view(row): return {'upload_id':row['id'],'filename':row['filename'],'created_at':row['created_at'],**json.loads(row['summary'])}

    def prepare(self,principal,session,body):
        exact(body,('request_key','upload_id','selected','rules'))
        text(body['request_key'],'请求标识',200);text(body['upload_id'],'上传编号',100)
        fingerprint=digest(body)
        with self.store.transaction():
            db=self.store._connect()
            old=db.execute('SELECT * FROM legacy_transfer_previews WHERE principal=? AND session=? AND request_key=?',(principal,session,body['request_key'])).fetchone()
            if old:
                if old['fingerprint']!=fingerprint: raise Conflict('预览请求标识已用于其他选择')
                return self.preview_view(old)
            upload=db.execute('SELECT * FROM legacy_transfer_uploads WHERE id=? AND principal=?',(body['upload_id'],principal)).fetchone()
            if not upload: raise Missing('上传文件不存在或不属于当前用户')
            package=json.loads(upload['payload'])
            plan=build_plan(self,principal,package,body['selected'],body['rules'],self.stamp())
            pid='TRV_'+uuid.uuid4().hex
            db.execute('INSERT INTO legacy_transfer_previews VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,principal,session,body['request_key'],fingerprint,upload['id'],canonical(plan),state_version(self.store,principal),self.clock()+1800,'pending',None))
            return self.preview_view(db.execute('SELECT * FROM legacy_transfer_previews WHERE id=?',(pid,)).fetchone())

    def preview_view(self,row):
        plan=json.loads(row['payload'])
        expired=row['status']=='pending' and row['expires_at']<self.clock()
        stale=row['status']=='pending' and row['base_version']!=state_version(self.store,row['principal'])
        status='expired' if expired else 'stale' if stale else row['status']
        return {'preview_id':row['id'],'upload_id':row['upload_id'],'request_key':row['request_key'],'status':status,'expires_at':row['expires_at'],
                'selected':plan['selected'],'rules':plan['rules'],'summary':plan['summary'],'warnings':plan['warnings'],'blockers':plan['blockers'],
                'requires_confirmation':True,'can_commit':status=='pending' and not plan['blockers'],'changes':page(plan.get('changes',[]),None,0,20),'receipt':json.loads(row['receipt']) if row['receipt'] else None}

    def owned(self,db,principal,session,pid):
        text(pid,'预览编号',100)
        row=db.execute('SELECT * FROM legacy_transfer_previews WHERE id=? AND principal=? AND session=?',(pid,principal,session)).fetchone()
        if not row: raise Missing('导入预览不存在或不属于当前会话')
        return row

    def commit(self,principal,session,body):
        exact(body,('preview_id','request_key'))
        with self.store.transaction():
            db=self.store._connect();row=self.owned(db,principal,session,body['preview_id'])
            if row['request_key']!=body['request_key']: raise Conflict('导入请求标识不匹配')
            if row['receipt']: return json.loads(row['receipt'])
            if row['status']!='pending': raise Conflict('导入已取消或失效')
            if row['expires_at']<self.clock(): raise Conflict('导入预览已过期，请重新选择并预览')
            if row['base_version']!=state_version(self.store,principal): raise Conflict('预览后正式数据已变化，请重新预览；本次尚未写入')
            plan=json.loads(row['payload'])
            if plan['blockers']: raise Invalid('存在不能映射的内容，请修改分类选择；不会部分提交')
            upload=db.execute('SELECT * FROM legacy_transfer_uploads WHERE id=? AND principal=?',(row['upload_id'],principal)).fetchone()
            if not upload: raise Missing('候选文件已移除')
            package=json.loads(upload['payload']);at=self.stamp()
            result=write_plan(self,principal,plan,package,row['id'],at)
            receipt={'status':'committed','batch_id':row['id'],'source_digest':package['source_digest'],'imported_at':at,'result':result,'warnings':plan['warnings'],'selected':plan['selected']}
            db.execute('INSERT INTO legacy_transfer_audit VALUES(?,?,?,?,?,?)',(row['id'],principal,package['source_digest'],canonical(plan['selected']),canonical(receipt),at))
            db.execute("UPDATE legacy_transfer_previews SET status='committed',receipt=? WHERE id=?",(canonical(receipt),row['id']))
            return receipt

    def status(self,principal,session,preview_id):
        with self.store.transaction(): return self.preview_view(self.owned(self.store._connect(),principal,session,preview_id))

    def preview_changes(self,principal,session,preview_id,*,category=None,offset=0,limit=50):
        with self.store.transaction():
            row=self.owned(self.store._connect(),principal,session,preview_id)
            return page(json.loads(row['payload']).get('changes',[]),category,offset,limit)

    def cancel(self,principal,session,preview_id):
        with self.store.transaction():
            db=self.store._connect();row=self.owned(db,principal,session,preview_id)
            if row['status']=='committed': raise Conflict('已提交的导入不能取消，请查看回执')
            db.execute("UPDATE legacy_transfer_previews SET status='cancelled' WHERE id=?",(row['id'],))
            return {'status':'cancelled','preview_id':row['id'],'message':'候选已取消，正式数据未改变'}

    def remove_upload(self,principal,session,upload_id):
        with self.store.transaction():
            db=self.store._connect()
            row=db.execute('SELECT id FROM legacy_transfer_uploads WHERE id=? AND principal=? AND session=?',(upload_id,principal,session)).fetchone()
            if not row: raise Missing('上传文件不存在')
            db.execute("UPDATE legacy_transfer_previews SET status='cancelled' WHERE upload_id=? AND status='pending'",(upload_id,))
            db.execute('DELETE FROM legacy_transfer_uploads WHERE id=?',(upload_id,))
            return {'removed':True,'notice':'只移除上传候选；已提交回执和正式记录保留'}

    def archive(self,principal,*,archive_id=None,category=None,offset=0,limit=30):
        with self.store.transaction():
            db=self.store._connect()
            if archive_id is not None:
                row=db.execute('SELECT * FROM legacy_transfer_archives WHERE id=? AND principal=?',(archive_id,principal)).fetchone()
                if not row: raise Missing('旧资料档案不存在')
                return {**{key:row[key] for key in ('id','category','title','source_id','imported_at')},'document':json.loads(row['document']),'source':json.loads(row['source'])}
            if type(offset) is not int or not 0<=offset<=100000 or type(limit) is not int or not 1<=limit<=100: raise Invalid('档案分页范围无效')
            if category not in (None,'holdings','watchlist','strategies','research','mandates'): raise Invalid('档案分类无效')
            where='principal=?'+(' AND category=?' if category else '')
            args=(principal,category) if category else (principal,)
            rows=db.execute('SELECT id,category,title,source_id,imported_at FROM legacy_transfer_archives WHERE '+where+' ORDER BY imported_at DESC,id LIMIT ? OFFSET ?',args+(limit,offset)).fetchall()
            total=db.execute('SELECT count(*) FROM legacy_transfer_archives WHERE '+where,args).fetchone()[0]
            return {'items':[dict(x) for x in rows],'total':total,'readonly':True,'notice':'旧资料仅供回看，不是 DSH 历史会话或本实例研究证据'}
