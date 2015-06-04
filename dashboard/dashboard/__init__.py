# Add required third-party libraries to sys.path.

import os
import sys

_THIRD_PARTY = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')
_THIRD_PARTY_PATHS = [
    os.path.join(_THIRD_PARTY, 'beautifulsoup4'),
    os.path.join(_THIRD_PARTY, 'google-api-python-client-1.4.0'),
    os.path.join(_THIRD_PARTY, 'mock-1.0.1'),
    os.path.join(_THIRD_PARTY, 'oauth2client-1.4.11'),
    os.path.join(_THIRD_PARTY, 'six-1.9.0'),
    os.path.join(_THIRD_PARTY, 'uritemplate-0.6'),
    os.path.join(_THIRD_PARTY, 'webtest'),
]

sys.path.extend(_THIRD_PARTY_PATHS)
