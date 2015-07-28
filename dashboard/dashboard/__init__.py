# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Add required third-party libraries to sys.path.

import os
import sys

_THIRD_PARTY_DIR = os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'third_party')

THIRD_PARTY_LIBRARIES = [
    'apiclient',
    'beautifulsoup4',
    'graphy',
    'mapreduce',
    'mock',
    'oauth2client',
    'six',
    'uritemplate',
    'webtest',
]


for library_dir in THIRD_PARTY_LIBRARIES:
  sys.path.append(os.path.join(_THIRD_PARTY_DIR, library_dir))
