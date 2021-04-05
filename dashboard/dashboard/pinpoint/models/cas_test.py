# Copyright 2021 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import datetime

import mock

from dashboard.pinpoint.models import cas
from dashboard.pinpoint.models.change import change_test
from dashboard.pinpoint import test


class CASReferenceTest(test.TestCase):

  def testPutAndGet(self):
    cas_references = (
        ('Mac Builder Perf', change_test.Change(1), 'target_name',
         'https://isolate.server', '7c7e90be'),
        ('Mac Builder Perf', change_test.Change(2), 'target_name',
         'https://isolate.server', '38e2f262'),
    )
    cas.Put(cas_references)

    cas_instance, cas_digest = cas.Get('Mac Builder Perf',
                                       change_test.Change(1),
                                       'target_name')
    self.assertEqual(cas_instance, 'https://isolate.server')
    self.assertEqual(cas_digest, '7c7e90be')

  def testUnknownCASReference(self):
    with self.assertRaises(KeyError):
      cas.Get('Wrong Builder', change_test.Change(1), 'target_name')

  @mock.patch.object(cas, 'datetime')
  def testExpiredCASReference(self, mock_datetime):
    cas_references = (('Mac Builder Perf', change_test.Change(1), 'target_name',
                       'https://isolate.server', '7c7e90be'),)
    cas.Put(cas_references)

    # Teleport to the future after the isolate is expired.
    mock_datetime.datetime.utcnow.return_value = (
        datetime.datetime.utcnow() + cas.CAS_EXPIRY_DURATION +
        datetime.timedelta(days=1))
    mock_datetime.timedelta = datetime.timedelta

    with self.assertRaises(KeyError):
      cas.Get('Mac Builder Perf', change_test.Change(1), 'target_name')
