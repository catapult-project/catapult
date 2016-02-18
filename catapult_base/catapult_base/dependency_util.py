# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

def GetChromeApkOsVersion(version_name):
  version = version_name[0]
  assert version.isupper(), (
      'First character of versions name %s was not an uppercase letter.')
  if version < 'L':
    return 'k'
  elif version > 'M':
    return 'n'
  return 'l'
