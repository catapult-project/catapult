# Add required third-party libraries to sys.path.

import os
import sys

_DASHBOARD_PARENT = os.path.join(os.path.dirname(__file__), os.path.pardir)
_THIRD_PARTY = os.path.join(_DASHBOARD_PARENT, os.path.pardir, 'third_party')
_THIRD_PARTY_PATHS = [
    os.path.join(_THIRD_PARTY, 'mock-1.0.1'),
    os.path.join(_THIRD_PARTY, 'webtest'),
    os.path.join(_THIRD_PARTY, 'oauth2client'),
]

sys.path.extend(_THIRD_PARTY_PATHS)
