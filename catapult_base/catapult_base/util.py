# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import sys


def GetCatapultDir():
  return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))


def IsRunningOnCrosDevice():
  """Returns True if we're on a ChromeOS device."""
  lsb_release = '/etc/lsb-release'
  if sys.platform.startswith('linux') and os.path.exists(lsb_release):
    with open(lsb_release, 'r') as f:
      res = f.read()
      if res.count('CHROMEOS_RELEASE_NAME'):
        return True
  return False


def _ExecutableExtensions():
  # pathext is, e.g. '.com;.exe;.bat;.cmd'
  exts = os.getenv('PATHEXT').split(';') #e.g. ['.com','.exe','.bat','.cmd']
  return [x[1:].upper() for x in exts] #e.g. ['COM','EXE','BAT','CMD']


def IsExecutable(path):
  if os.path.isfile(path):
    if hasattr(os, 'name') and os.name == 'nt':
      return path.split('.')[-1].upper() in _ExecutableExtensions()
    else:
      return os.access(path, os.X_OK)
  else:
    return False
