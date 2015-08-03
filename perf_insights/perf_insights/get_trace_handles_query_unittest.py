# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import operator
import unittest

from perf_insights import get_trace_handles_query

class FilterTests(unittest.TestCase):
  def testEqNumber(self):
    f = get_trace_handles_query.Filter.FromString("a = 3")
    self.assertEquals(f.field, 'a')
    self.assertEquals(f.op, operator.eq)
    self.assertEquals(f.constant, 3)

    self.assertFalse(f.Eval({'a': 4}))
    self.assertTrue(f.Eval({'a': 3}))

  def testInTuple(self):
    f = get_trace_handles_query.Filter.FromString("a IN (1, 2)")
    self.assertEquals(f.field, 'a');
    self.assertEquals(f.op, get_trace_handles_query._InOp);
    self.assertEquals(f.constant, (1, 2));

    self.assertFalse(f.Eval({'a': 3}))
    self.assertTrue(f.Eval({'a': 1}))

  def testInTupleStr(self):
    f = get_trace_handles_query.Filter.FromString("a IN ('a', 'b')")
    self.assertEquals(f.field, 'a');
    self.assertEquals(f.op, get_trace_handles_query._InOp);
    self.assertEquals(f.constant, ('a', 'b'));

    self.assertFalse(f.Eval({'a': 'c'}))
    self.assertTrue(f.Eval({'a': 'a'}))



class GetTraceHandlesQueryTests(unittest.TestCase):
  def testSimple(self):
    q = get_trace_handles_query.GetTraceHandlesQuery.FromString('')
    self.assertTrue(q.IsMetadataInteresting({'a': 1}))

  def testSimpleOp(self):
    q = get_trace_handles_query.GetTraceHandlesQuery.FromString('a = 3')
    self.assertFalse(q.IsMetadataInteresting({'a': 1}))
    self.assertTrue(q.IsMetadataInteresting({'a': 3}))

  def testMultipleFiltersOp(self):
    q = get_trace_handles_query.GetTraceHandlesQuery.FromString(
        'a = 3 AND b = 4')
    self.assertFalse(q.IsMetadataInteresting({'a': 1, 'b': 1}))
    self.assertFalse(q.IsMetadataInteresting({'a': 3, 'b': 1}))
    self.assertFalse(q.IsMetadataInteresting({'a': 1, 'b': 4}))
    self.assertTrue(q.IsMetadataInteresting({'a': 3, 'b': 4}))

