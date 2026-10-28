"""从现有权威领域构造只读上下文；旧算法的写入只落本机学习文档。"""
import copy
import json
from datetime import datetime,timezone
from ..investment.service import Investment
from ..strategies.storage import Documents
from ..execution import digest

class Snapshot:
    def __init__(self,store,principal,document):
        self.value=copy.deepcopy(document)
        facts=Investment(store).read(principal)
        strategies=Documents(store,principal)
        self.readonly={c:strategies.all(c) for c in ('strategies','shadow_equity','shadows')}
        self.readonly['holdings']={'default':facts['holdings']}
        self.readonly['watchlist']={'default':[x['ticker'] for x in facts['watchlist']]}
        self.profile=(facts['risk_profile'] or {}).get('profile','balanced')
        self.explicit_profile=facts['risk_profile'] is not None
        self.holdings_status=facts['holdings_status']
        self.position_alerts=store.position_risk.alerts(principal) if getattr(store,'position_risk',None) else []
        self.value.setdefault('preferences',{}).update(risk_profile=self.profile,kyc={'answers':(facts['risk_profile'] or {}).get('answers',[])})
        raw=[json.loads(r[0]) for r in store._connect().execute('SELECT document FROM strategy_events WHERE principal=? ORDER BY observed_at DESC,id LIMIT 100',(principal,))]
        self.events=[]
        for e in raw:
            e=copy.deepcopy(e)
            e['tickers']=[{'code':x['code'],'name':x.get('name',x['code'])} for x in e.get('securities',[]) if x.get('code')]
            e['time']=datetime.fromtimestamp(e['observed_at']).strftime('%Y-%m-%d %H:%M:%S')
            self.events.append(e)
        self.context_version=digest([facts['version'],strategies.version(),raw,self.position_alerts])
    def context(self):return {'profile':self.profile,'events':self.events,'position_alerts':self.position_alerts}
    def all(self,collection):return copy.deepcopy(self.readonly.get(collection,self.value.get(collection,{})))
    def get(self,collection,key,default=None):return self.all(collection).get(key,default)
    def set(self,collection,key,value):
        if collection not in ('preferences','behavior'):raise ValueError('不能改写只读业务快照')
        self.value.setdefault(collection,{})[key]=copy.deepcopy(value);return value
    def mutate_document(self,collection,transform):
        if collection not in ('preferences','behavior'):raise ValueError('不能改写只读业务快照')
        self.value[collection]=transform(self.all(collection));return copy.deepcopy(self.value[collection])
    def persistent(self):
        # 显式画像只由投资事实持有；不能形成第二份长期风险偏好。
        value=copy.deepcopy(self.value)
        value.get('preferences',{}).pop('risk_profile',None)
        value.get('preferences',{}).pop('kyc',None)
        return value
