# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from perf_insights.mre import failure as failure_module


class FailureTests(unittest.TestCase):

  def testAsDict(self):
    failure = failure_module.Failure(None, 'foo.html:Foo', 'file://foo.html',
                                     'err', 'desc', 'stack')

    self.assertEquals(failure.AsDict(), {
      'function_handle_string': 'foo.html:Foo',
      'trace_canonical_url': 'file://foo.html',
      'type': 'err',
      'description': 'desc',
      'stack': 'stack'
    })

  def testFromDict(self):
    failure_dict = {
        'function_handle_string': 'foo.html:Foo',
        'trace_canonical_url': 'file://foo.html',
        'type': 'err',
        'description': 'desc',
        'stack': 'stack'
    }

    failure = failure_module.Failure.FromDict(failure_dict)

    self.assertEquals(failure.function_handle_string, 'foo.html:Foo')
    self.assertEquals(failure.trace_canonical_url, 'file://foo.html')
    self.assertEquals(failure.failure_type_name, 'err')
    self.assertEquals(failure.description, 'desc')
    self.assertEquals(failure.stack, 'stack')
