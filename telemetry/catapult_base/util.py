# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys


def GetCatapultDir():
  return os.path.normpath(os.path.join(
      os.path.dirname(__file__), '..', '..', '..', 'third_party', 'catapult'))


def IsRunningOnCrosDevice():
  """Returns True if we're on a ChromeOS device."""
  lsb_release = '/etc/lsb-release'
  if sys.platform.startswith('linux') and os.path.exists(lsb_release):
    with open(lsb_release, 'r') as f:
      res = f.read()
      if res.count('CHROMEOS_RELEASE_NAME'):
        return True
  return False


def IsExecutable(path):
  return os.path.isfile(path) and os.access(path, os.X_OK)
