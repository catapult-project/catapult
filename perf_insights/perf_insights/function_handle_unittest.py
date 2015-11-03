# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from perf_insights import function_handle

class FunctionHandleTests(unittest.TestCase):

  def testRepr(self):
    handle0 = function_handle.FunctionHandle(filename='foo.html')
    handle1 = function_handle.FunctionHandle(function_name='Bar')

    self.assertEquals(
        str(handle0),
        'FunctionHandle(filename="foo.html")')

    self.assertEquals(
        str(handle1),
        'FunctionHandle(function_name="Bar")')

  def testAsDict(self):
    handle0 = function_handle.FunctionHandle(filename='foo.html')
    handle1 = function_handle.FunctionHandle(function_name='Bar')

    self.assertEquals(handle0.AsDict(), {
        'filename': 'foo.html'
    })

    self.assertEquals(handle1.AsDict(), {
        'function_name': 'Bar'
    })
