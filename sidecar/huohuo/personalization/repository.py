"""本机学习领域的 SQLite 端口；复合业务与原实例共享事务。"""
import json
from ..contracts import canonical
from ..execution import Conflict,Missing,digest

class Repository:
    def __init__(self,store):self.store=store
    def transaction(self):return self.store.transaction()
    def load(self,principal):
        row=self.store._connect().execute('SELECT version,document FROM personalization_state WHERE principal=?',(principal,)).fetchone()
        return (row[0],json.loads(row[1])) if row else (0,{'preferences':{'local_learning':{'enabled':False}},'behavior':{'events':[],'default':[]}})
    def save(self,principal,version,document,action,detail,at):
        self.store._connect().execute('INSERT INTO personalization_state VALUES(?,?,?) ON CONFLICT(principal) DO UPDATE SET version=excluded.version,document=excluded.document',(principal,version,canonical(document)))
        self.store._connect().execute('INSERT INTO personalization_audit VALUES(?,?,?,?,?)',(principal,version,action,canonical(detail),at))
    def preview(self,pid,principal,version,context_version,payload):
        self.store._connect().execute('INSERT INTO personalization_previews VALUES(?,?,?,?,?)',(pid,principal,version,context_version,canonical(payload)))
    def get_preview(self,principal,pid):
        row=self.store._connect().execute('SELECT * FROM personalization_previews WHERE principal=? AND id=?',(principal,pid)).fetchone()
        if not row:raise Missing('偏好预览不存在或不属于当前用户')
        return {**dict(row),'payload':json.loads(row['payload'])}
    def receipt(self,principal,key,body):
        row=self.store._connect().execute('SELECT * FROM personalization_receipts WHERE principal=? AND request_key=?',(principal,key)).fetchone()
        if row:
            if row['fingerprint']!=digest(body):raise Conflict('请求标识已用于其他偏好操作')
            return json.loads(row['result'])
    def record_receipt(self,principal,key,body,result):
        self.store._connect().execute('INSERT INTO personalization_receipts VALUES(?,?,?,?)',(principal,key,digest(body),canonical(result)))
    def purge_learning_history(self,principal,current_preview):
        db=self.store._connect()
        db.execute("DELETE FROM personalization_audit WHERE principal=? AND action IN ('reading','feedback','retention')",(principal,))
        db.execute('DELETE FROM personalization_previews WHERE principal=? AND id!=?',(principal,current_preview))
        db.execute('DELETE FROM personalization_receipts WHERE principal=?',(principal,))
