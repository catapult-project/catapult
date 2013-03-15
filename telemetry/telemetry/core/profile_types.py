# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

PROFILE_TYPE_MAPPING = {
  'typical_user': 'chrome/test/data/extensions/profiles/content_scripts1',
  'power_user': 'chrome/test/data/extensions/profiles/extension_webrequest',
}
PROFILE_TYPES = PROFILE_TYPE_MAPPING.keys()

def GetProfileDir(profile_type):
  path = os.path.abspath(os.path.join(os.path.dirname(__file__),
      '..', '..', '..', '..', *PROFILE_TYPE_MAPPING[profile_type].split('/')))
  assert os.path.exists(path)
  return path
