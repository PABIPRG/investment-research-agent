"""只读集合端口：不创建委托、不写投资事实、读取失败绝不当成空集合。"""
from ..contracts import Invalid

class CollectionProvider:
    def __init__(self,investment,principal):self.investment,self.principal=investment,principal
    def read_snapshot(self,collection_type,version=None):
        if collection_type not in ('holdings','watchlist'):raise Invalid('集合仅支持持仓或自选')
        facts=self.investment.read(self.principal) if version is None else self.investment.snapshot(self.principal,version)
        rows=facts[collection_type]
        return {'collection':collection_type,'fact_version':facts['version'],'status':'not_recorded' if facts[collection_type+'_status']=='not_recorded' else 'ready' if rows else 'empty',
                'members':[{'entity_id':'SEC:CN:A:'+x['ticker'],'name':x.get('name') or x['ticker']} for x in rows]}

    def get_collection(self,collection_type):
        """兼容 research_entities.ports.CollectionProvider；未知与读取异常不伪装空。"""
        from ..research_entities.models import EntityCollection
        from ..execution import digest
        snap=self.read_snapshot(collection_type)
        if snap['status']=='not_recorded':return None
        return EntityCollection(collection_id='investment:'+digest([self.principal,collection_type]),collection_type=collection_type,source='investment',member_entity_ids=[x['entity_id'] for x in snap['members']],filter_definition={'fact_version':snap['fact_version']},authorization_status='authorized')
