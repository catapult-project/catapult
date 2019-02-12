# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from tracing.value import histogram_deserializer


class HistogramDeserializerUnittest(unittest.TestCase):
  def testObjects(self):
    deserializer = histogram_deserializer.HistogramDeserializer(['a', ['b']])
    self.assertEqual('a', deserializer.GetObject(0))
    self.assertEqual(['b'], deserializer.GetObject(1))
    with self.assertRaises(IndexError):
      deserializer.GetObject(2)
