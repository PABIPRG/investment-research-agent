from ...investment.risk_profiles import DEFAULT_PROFILE, RISK_PROFILES, profile
from .runtime import _current

def get_risk_profile(params=None):
    return _current.get()['profile']
