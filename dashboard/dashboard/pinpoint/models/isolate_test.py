# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from google.appengine.ext import ndb
from google.appengine.ext import testbed

from dashboard.pinpoint.models import change
from dashboard.pinpoint.models import isolate


_CHANGE_1 = change.Change(change.Dep('chromium', 'f9f2b720'))
_CHANGE_2 = change.Change(change.Dep('chromium', 'f35be4f1'))


class IsolateTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    ndb.get_context().clear_cache()

  def tearDown(self):
    self.testbed.deactivate()

  def testPutAndGet(self):
    isolate.Put((
        ('Mac Builder', _CHANGE_1, 'telemetry_perf', '7c7e90be'),
        ('Mac Builder', _CHANGE_2, 'telemetry_perf', '38e2f262')))

    isolate_hash = isolate.Get('Mac Builder', _CHANGE_1, 'telemetry_perf')
    self.assertEqual(isolate_hash, '7c7e90be')

  def testUnknownIsolate(self):
    with self.assertRaises(KeyError):
      isolate.Get('Wrong Builder', _CHANGE_1, 'telemetry_perf')
