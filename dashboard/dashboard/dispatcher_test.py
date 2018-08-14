# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import unittest


class DispatcherTest(unittest.TestCase):

  def testImport(self):
    # load_from_prod requires this:
    os.environ['APPLICATION_ID'] = 'test-dot-chromeperf'

    # gae_ts_mon requires these:
    os.environ['CURRENT_MODULE_ID'] = ''
    os.environ['CURRENT_VERSION_ID'] = ''

    from dashboard import dispatcher


if __name__ == '__main__':
  unittest.main()
