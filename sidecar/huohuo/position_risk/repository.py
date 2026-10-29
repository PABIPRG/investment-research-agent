from ..contracts import canonical

class Bindings:
    def __init__(self,store):self.store=store
    def all(self,principal):return [dict(r) for r in self.store._connect().execute('SELECT * FROM position_risk_bindings WHERE principal=? ORDER BY ticker,kind',(principal,))]
    def for_mandate(self,mid):
        row=self.store._connect().execute('SELECT * FROM position_risk_bindings WHERE mandate_id=?',(mid,)).fetchone()
        return dict(row) if row else None
    def principals(self):return [r[0] for r in self.store._connect().execute('SELECT DISTINCT principal FROM position_risk_bindings WHERE alive=1')]
    def put(self,value):
        self.store._connect().execute('INSERT INTO position_risk_bindings VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(principal,ticker,kind) DO UPDATE SET config_key=excluded.config_key,mandate_id=excluded.mandate_id,basis_cost=excluded.basis_cost,resolved_price=excluded.resolved_price,generation=excluded.generation,alive=excluded.alive',
            tuple(value[k] for k in ('principal','ticker','kind','config_key','mandate_id','basis_cost','resolved_price','generation','alive')))
    def deactivate(self,principal,code,kind):
        self.store._connect().execute('UPDATE position_risk_bindings SET alive=0 WHERE principal=? AND ticker=? AND kind=?',(principal,code,kind))
    def consumed(self,mid,exclude=None):
        return self.store._connect().execute("SELECT 1 FROM contact_decisions WHERE mandate_id=? AND decision='send' AND (? IS NULL OR decision_id!=?) LIMIT 1",(mid,exclude,exclude)).fetchone() is not None
    def decisions(self,principal):
        import json
        rows=self.store._connect().execute("SELECT d.decision_id,d.created_at,d.detail,d.mandate_id,r.basis_json FROM contact_decisions d JOIN mandates m USING(mandate_id) JOIN mandate_revisions r ON r.mandate_id=d.mandate_id AND r.revision=d.mandate_revision WHERE m.principal_id=? AND d.decision='send' AND json_extract(r.basis_json,'$.position_risk') IS NOT NULL ORDER BY d.created_at DESC LIMIT 100",(principal,))
        return [{**dict(r),'position_risk':json.loads(r['basis_json'])['position_risk']} for r in rows]
