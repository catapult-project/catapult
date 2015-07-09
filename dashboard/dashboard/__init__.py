# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Add required third-party libraries to sys.path.

import os
import sys

_THIRD_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')

THIRD_PARTY_LIBRARIES = [
    'beautifulsoup4',
    'google-api-python-client-1.4.0',
    'GoogleAppEngineMapReduce-1.9.22.0',
    'Graphy-1.0.0',
    'mock-1.0.1',
    'oauth2client-1.4.11',
    'six-1.9.0',
    'uritemplate-0.6',
    'webtest',
    #'pg8000-1.10.2',
    #'simplejson-3.7.3',
]


for library_dir in THIRD_PARTY_LIBRARIES:
  sys.path.append(os.path.join(_THIRD_PARTY_DIR, library_dir))
