# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from tracing.build import temporary_dev_server


class DevServerTests(unittest.TestCase):

  def setUp(self):
    self.server = temporary_dev_server.TemporaryDevServer()

  def tearDown(self):
    self.server.Close()
