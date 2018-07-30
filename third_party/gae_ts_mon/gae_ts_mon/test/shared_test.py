# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import gae_ts_mon

from infra_libs.ts_mon import shared
from testing_utils import testing


class SharedTest(testing.AppengineTestCase):
  def test_get_instance_entity(self):
    entity = shared.get_instance_entity()
    # Save the modification, make sure it sticks.
    entity.task_num = 42
    entity.put()
    entity2 = shared.get_instance_entity()
    self.assertEqual(42, entity2.task_num)

    # Make sure it does not pollute the default namespace.
    self.assertIsNone(shared.Instance.get_by_id(entity.key.id()))
