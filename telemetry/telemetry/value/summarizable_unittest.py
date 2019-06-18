# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from telemetry.value import summarizable

class SummarizableTest(unittest.TestCase):

  def testAsDictWithoutImprovementDirection(self):
    value = summarizable.SummarizableValue(
        None, 'foo', 'bars', important=False, description='desc',
        improvement_direction=None)

    self.assertNotIn('improvement_direction', value.AsDict())

  def testAsDictWithInvalidImprovementDirection(self):
    # TODO(eakuefner): Remove this test when we check I.D. in constructor
    value = summarizable.SummarizableValue(
        None, 'foo', 'bars', important=False, description='desc',
        improvement_direction='baz')

    self.assertNotIn('improvement_direction', value.AsDict())
