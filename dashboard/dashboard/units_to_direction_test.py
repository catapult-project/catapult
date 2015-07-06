# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for units_to_direction module."""

import unittest

from dashboard import testing_common
from dashboard import units_to_direction
from dashboard.models import anomaly


class UnitsToDirectionTest(testing_common.TestCase):

  def testBasic(self):
    units_to_direction.UpdateFromJson({
        'description': 'foo',
        'foo': {'improvement_direction': 'down'},
        'bar': {'improvement_direction': 'up'},
    })

    self.assertEqual(anomaly.DOWN,
                     units_to_direction.GetImprovementDirectionForUnit('foo'))
    self.assertEqual(anomaly.UP,
                     units_to_direction.GetImprovementDirectionForUnit('bar'))
    self.assertEqual(
        anomaly.UNKNOWN,
        units_to_direction.GetImprovementDirectionForUnit('does-not-exist'))

  def testAdd(self):
    units_to_direction.UpdateFromJson({
        'description': 'foo',
        'foo': {'improvement_direction': 'down'},
    })

    self.assertEqual(anomaly.UNKNOWN,
                     units_to_direction.GetImprovementDirectionForUnit('bar'))

    units_to_direction.UpdateFromJson({
        'description': 'foo',
        'foo': {'improvement_direction': 'down'},
        'bar': {'improvement_direction': 'up'},
    })

    self.assertEqual(anomaly.UP,
                     units_to_direction.GetImprovementDirectionForUnit('bar'))

  def testRemove(self):
    units_to_direction.UpdateFromJson({
        'description': 'foo',
        'foo': {'improvement_direction': 'down'},
        'bar': {'improvement_direction': 'up'},
    })

    self.assertEqual(anomaly.UP,
                     units_to_direction.GetImprovementDirectionForUnit('bar'))

    units_to_direction.UpdateFromJson({
        'description': 'foo',
        'foo': {'improvement_direction': 'down'},
    })

    self.assertEqual(anomaly.UNKNOWN,
                     units_to_direction.GetImprovementDirectionForUnit('bar'))

  def testUpdate(self):
    units_to_direction.UpdateFromJson({
        'description': 'foo',
        'foo': {'improvement_direction': 'down'},
    })

    self.assertEqual(anomaly.DOWN,
                     units_to_direction.GetImprovementDirectionForUnit('foo'))

    units_to_direction.UpdateFromJson({
        'description': 'foo',
        'foo': {'improvement_direction': 'up'},
    })

    self.assertEqual(anomaly.UP,
                     units_to_direction.GetImprovementDirectionForUnit('foo'))


if __name__ == '__main__':
  unittest.main()
