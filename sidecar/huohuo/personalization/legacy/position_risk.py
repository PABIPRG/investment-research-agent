from copy import deepcopy
from .runtime import _current
def trigger_alert_items(store):return deepcopy(_current.get().get('position_alerts',[]))
