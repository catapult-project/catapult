# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from dashboard.pinpoint.models.change import change_test
from dashboard.pinpoint.models import isolate
from dashboard.pinpoint import test


class IsolateTest(test.TestCase):

  def testPutAndGet(self):
    isolate_infos = (
        ('Mac Builder Perf', change_test.Change(1), 'target_name',
         'https://isolate.server', '7c7e90be'),
        ('Mac Builder Perf', change_test.Change(2), 'target_name',
         'https://isolate.server', '38e2f262'),
    )
    isolate.Put(isolate_infos)

    isolate_server, isolate_hash = isolate.Get(
        'Mac Builder Perf', change_test.Change(1), 'target_name')
    self.assertEqual(isolate_server, 'https://isolate.server')
    self.assertEqual(isolate_hash, '7c7e90be')

  def testUnknownIsolate(self):
    with self.assertRaises(KeyError):
      isolate.Get('Wrong Builder', change_test.Change(1), 'target_name')

  def testBuilderNameMap(self):
    # TODO(dtu): Remove 6 months after LUCI migration is complete.
    isolate_infos = (
        ('android_arm64-builder-perf', change_test.Change(1),
         'target_name', 'https://isolate.server', 'abcd1234'),
    )
    isolate.Put(isolate_infos)

    isolate_server, isolate_hash = isolate.Get(
        'Android arm64 Compile Perf', change_test.Change(1), 'target_name')
    self.assertEqual(isolate_server, 'https://isolate.server')
    self.assertEqual(isolate_hash, 'abcd1234')

    with self.assertRaises(KeyError):
      isolate.Get('Android arm64 Compile Perf',
                  change_test.Change(2), 'target_name')
