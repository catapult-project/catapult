# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import operator
import unittest

from perf_insights import get_trace_handles_query

class FilterTests(unittest.TestCase):
  def testEqNumber(self):
    f = get_trace_handles_query.Filter.FromString("a = 3")

    self.assertEquals(f.a.fieldName, 'a')
    self.assertEquals(f.op, operator.eq)
    self.assertEquals(f.b.constant, 3)

    self.assertFalse(f.Eval({'a': 4}))
    self.assertTrue(f.Eval({'a': 3}))

  def testInTuple(self):
    f = get_trace_handles_query.Filter.FromString("a IN (1, 2)")
    self.assertEquals(f.a.fieldName, 'a');
    self.assertEquals(f.op, get_trace_handles_query._InOp);
    self.assertEquals(f.b.constant, (1, 2));

    self.assertFalse(f.Eval({'a': 3}))
    self.assertTrue(f.Eval({'a': 1}))

  def testInTupleStr(self):
    f = get_trace_handles_query.Filter.FromString("a IN ('a', 'b')")
    self.assertEquals(f.a.fieldName, 'a');
    self.assertEquals(f.op, get_trace_handles_query._InOp);
    self.assertEquals(f.b.constant, ('a', 'b'));

    self.assertFalse(f.Eval({'a': 'c'}))
    self.assertTrue(f.Eval({'a': 'a'}))

  def testTupleInMetdata(self):
    f = get_trace_handles_query.Filter.FromString("'c' IN tags")
    self.assertEquals(f.a.constant, 'c');
    self.assertEquals(f.op, get_trace_handles_query._InOp);
    self.assertEquals(f.b.fieldName, 'tags');

    self.assertFalse(f.Eval({'tags': ('a', 'b')}))
    self.assertTrue(f.Eval({'tags': ('a', 'b', 'c')}))

  def testDateComparison(self):
    f = get_trace_handles_query.Filter.FromString(
        "date >= Date(2015-01-02 3:04:05.678)")
    self.assertEquals(f.a.fieldName, 'date');
    self.assertEquals(f.op, operator.ge);

    self.assertTrue(isinstance(f.b.constant, datetime.datetime));
    at = datetime.datetime(2015, 1, 2, 3, 4, 5, 678000)
    self.assertEquals(f.b.constant, at)

    before = datetime.datetime(2014, 12, 1, 2, 3, 4, 0)
    self.assertFalse(f.Eval({'date': before}))

    after = datetime.datetime(2015, 2, 3, 4, 5, 6, 789000)
    self.assertTrue(f.Eval({'date': at}))
    self.assertTrue(f.Eval({'date': after}))


class GetTraceHandlesQueryTests(unittest.TestCase):
  def testSimple(self):
    q = get_trace_handles_query.GetTraceHandlesQuery.FromString('')
    self.assertTrue(q.Eval({'a': 1}))

  def testSimpleOp(self):
    q = get_trace_handles_query.GetTraceHandlesQuery.FromString('a = 3')
    self.assertFalse(q.Eval({'a': 1}))
    self.assertTrue(q.Eval({'a': 3}))

  def testMultipleFiltersOp(self):
    q = get_trace_handles_query.GetTraceHandlesQuery.FromString(
        'a = 3 AND b = 4')
    self.assertFalse(q.Eval({'a': 1, 'b': 1}))
    self.assertFalse(q.Eval({'a': 3, 'b': 1}))
    self.assertFalse(q.Eval({'a': 1, 'b': 4}))
    self.assertTrue(q.Eval({'a': 3, 'b': 4}))

  def testDateRange(self):
    f = get_trace_handles_query.GetTraceHandlesQuery.FromString(
        'date >= Date(2015-01-01 00:00:00.00) AND ' +
        'date < Date(2015-02-01 00:00:00.00)')

    just_before_start = datetime.datetime(2014, 12, 31, 23, 59, 59, 99999)
    start = datetime.datetime(2015, 1, 1, 0, 0, 0, 0)
    end = datetime.datetime(2015, 2, 1, 0, 0, 0, 0)
    just_before_end = datetime.datetime(2015, 1, 31, 23, 59, 59, 999999)
    middle = datetime.datetime(2015, 1, 15, 0, 0, 0, 0)
    way_after = datetime.datetime(2015, 3, 1, 0, 0, 0, 0)

    self.assertFalse(f.Eval({'date': just_before_start}))
    self.assertTrue(f.Eval({'date': start}))
    self.assertTrue(f.Eval({'date': middle}))
    self.assertTrue(f.Eval({'date': just_before_end}))
    self.assertFalse(f.Eval({'date': end}))
    self.assertFalse(f.Eval({'date': way_after}))

