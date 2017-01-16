#!/usr/bin/env python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import posixpath
import unittest

from devil.android import flag_changer


_CMDLINE_FILE = 'chrome-command-line'


class _FakeDevice(object):
  def __init__(self):
    self.build_type = 'user'
    self.has_root = True
    self.file_system = {}

  def HasRoot(self):
    return self.has_root

  def PathExists(self, filepath):
    return filepath in self.file_system

  def RemovePath(self, path, **_kwargs):
    self.file_system.pop(path)

  def WriteFile(self, path, contents, **_kwargs):
    self.file_system[path] = contents

  def ReadFile(self, path, **_kwargs):
    return self.file_system[path]


class FlagChangerTest(unittest.TestCase):
  def setUp(self):
    self.device = _FakeDevice()
    # pylint: disable=protected-access
    self.cmdline_path = posixpath.join(flag_changer._CMDLINE_DIR, _CMDLINE_FILE)
    self.cmdline_path_legacy = posixpath.join(
        flag_changer._CMDLINE_DIR_LEGACY, _CMDLINE_FILE)

  def testFlagChanger_removeLegacyCmdLine(self):
    self.device.WriteFile(self.cmdline_path_legacy, 'chrome --old --stuff')
    self.assertTrue(self.device.PathExists(self.cmdline_path_legacy))

    changer = flag_changer.FlagChanger(self.device, 'chrome-command-line')
    self.assertEquals(
        changer._cmdline_path,  # pylint: disable=protected-access
        self.cmdline_path)
    self.assertFalse(self.device.PathExists(self.cmdline_path_legacy))


if __name__ == '__main__':
  unittest.main(verbosity=2)
