# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os

from telemetry import crx_id

class ExtensionPathNonExistentException(Exception):
  pass

class ExtensionToLoad(object):
  def __init__(self, path):
    if not os.path.isdir(path):
      raise ExtensionPathNonExistentException(
          'Extension path not a directory %s' % path)
    self.path = path

  def extension_id(self):
    return crx_id.GetCRXAppID(os.path.abspath(self.path))
