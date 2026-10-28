"""旧算法的数据接口适配至实例 SQLite；复合动作由外层事务原子提交。"""
import json
from ..contracts import canonical
from ..execution import digest

class Documents:
    def __init__(self, store, principal):self.store,self.principal=store,principal
    def all(self, collection):
        return {r['id']:json.loads(r['document']) for r in self.store._connect().execute(
            'SELECT id,document FROM strategy_documents WHERE principal=? AND collection=? ORDER BY id',
            (self.principal,collection))}
    def get(self,collection,key,default=None):
        row=self.store._connect().execute('SELECT document FROM strategy_documents WHERE principal=? AND collection=? AND id=?',
                                        (self.principal,collection,key)).fetchone()
        return json.loads(row[0]) if row else default
    def set(self,collection,key,value):
        self.store._connect().execute('INSERT INTO strategy_documents VALUES(?,?,?,?) ON CONFLICT(principal,collection,id) DO UPDATE SET document=excluded.document',
                                     (self.principal,collection,key,canonical(value)))
        return value
    def update(self,collection,key,**fields):return self.set(collection,key,{**(self.get(collection,key) or {}),**fields})
    def mutate(self,collection,key,transform,default=None):return self.set(collection,key,transform(self.get(collection,key,default)))
    def delete(self,collection,key):
        self.store._connect().execute('DELETE FROM strategy_documents WHERE principal=? AND collection=? AND id=?',(self.principal,collection,key))
    def version(self):
        return digest([dict(r) for r in self.store._connect().execute(
            "SELECT collection,id,document FROM strategy_documents WHERE principal=? AND collection NOT IN ('evolution_previews') ORDER BY collection,id",(self.principal,))])
