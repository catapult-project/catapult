# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import unittest

from tracing import value as value_module


class ValueTests(unittest.TestCase):

  def testScalar(self):
    d = {
        'canonical_url': '/a.json',
        'type': 'scalar',
        'name': 'MyScalarValue',
        'important': False,
        'value': {'a': 1, 'b': 'b'}
    }
    v = value_module.Value.FromDict(d)
    self.assertTrue(isinstance(v, value_module.ScalarValue))
    d2 = v.AsDict()

    self.assertEquals(d, d2)

  def testDict(self):
    d = {
        'canonical_url': '/a.json',
        'type': 'dict',
        'name': 'MyDictValue',
        'important': False,
        'value': {'a': 1, 'b': 'b'}
    }
    v = value_module.Value.FromDict(d)
    self.assertTrue(isinstance(v, value_module.DictValue))
    d2 = v.AsDict()

    self.assertEquals(d, d2)

  def testFailure(self):
    d = {
        'canonical_url': '/a.json',
        'type': 'failure',
        'name': 'Error',
        'important': False,
        'description': 'Some error message',
        'stack_str': 'Some stack string'
    }
    v = value_module.Value.FromDict(d)
    self.assertTrue(isinstance(v, value_module.FailureValue))
    d2 = v.AsDict()

    self.assertEquals(d, d2)
