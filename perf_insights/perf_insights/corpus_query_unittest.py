# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import operator
import unittest

from perf_insights import corpus_query


class FilterTests(unittest.TestCase):

  def testEqNumber(self):
    f = corpus_query.Filter.FromString("a = 3")

    self.assertEquals(f.a.fieldName, 'a')
    self.assertEquals(f.op, operator.eq)
    self.assertEquals(f.b.constant, 3)

    self.assertFalse(f.Eval({'a': 4}))
    self.assertTrue(f.Eval({'a': 3}))

  def testInTuple(self):
    f = corpus_query.Filter.FromString("a IN (1, 2)")
    self.assertEquals(f.a.fieldName, 'a')
    self.assertEquals(f.op, corpus_query._InOp)
    self.assertEquals(f.b.constant, (1, 2))

    self.assertFalse(f.Eval({'a': 3}))
    self.assertTrue(f.Eval({'a': 1}))

  def testInTupleStr(self):
    f = corpus_query.Filter.FromString("a IN ('a', 'b')")
    self.assertEquals(f.a.fieldName, 'a')
    self.assertEquals(f.op, corpus_query._InOp)
    self.assertEquals(f.b.constant, ('a', 'b'))

    self.assertFalse(f.Eval({'a': 'c'}))
    self.assertTrue(f.Eval({'a': 'a'}))

  def testPropertyAndValueOrder(self):
    with self.assertRaises(Exception):
      corpus_query.Filter.FromString("'c' IN tags")
    with self.assertRaises(Exception):
      corpus_query.Filter.FromString("'test' = a")
    with self.assertRaises(Exception):
      corpus_query.Filter.FromString("'test' = 'test'")
    with self.assertRaises(Exception):
      corpus_query.Filter.FromString("a = b")

  def testDateComparison(self):
    f = corpus_query.Filter.FromString(
        "date >= Date(2015-01-02 3:04:05.678)")
    self.assertEquals(f.a.fieldName, 'date')
    self.assertEquals(f.op, operator.ge)

    self.assertTrue(isinstance(f.b.constant, datetime.datetime))
    at = datetime.datetime(2015, 1, 2, 3, 4, 5, 678000)
    self.assertEquals(f.b.constant, at)

    before = datetime.datetime(2014, 12, 1, 2, 3, 4, 0)
    self.assertFalse(f.Eval({'date': before}))

    after = datetime.datetime(2015, 2, 3, 4, 5, 6, 789000)
    self.assertTrue(f.Eval({'date': at}))
    self.assertTrue(f.Eval({'date': after}))


class CorpusQueryTests(unittest.TestCase):

  def testSimple(self):
    q = corpus_query.CorpusQuery.FromString('')
    self.assertTrue(q.Eval({'a': 1}))

  def testSimpleOp(self):
    q = corpus_query.CorpusQuery.FromString('a = 3')
    self.assertFalse(q.Eval({'a': 1}))
    self.assertTrue(q.Eval({'a': 3}))

  def testMultipleFiltersOp(self):
    q = corpus_query.CorpusQuery.FromString(
        'a = 3 AND b = 4')
    self.assertFalse(q.Eval({'a': 1, 'b': 1}))
    self.assertFalse(q.Eval({'a': 3, 'b': 1}))
    self.assertFalse(q.Eval({'a': 1, 'b': 4}))
    self.assertTrue(q.Eval({'a': 3, 'b': 4}))

  def testDateRange(self):
    f = corpus_query.CorpusQuery.FromString(
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

  def testSimpleOpWithMaxTraceHandles(self):
    q = corpus_query.CorpusQuery.FromString('a = 3 AND MAX_TRACE_HANDLES=3')
    self.assertTrue(q.Eval({'a': 3}, 0))
    self.assertFalse(q.Eval({'a': 3}, 3))
    self.assertFalse(q.Eval({'a': 3}, 4))

  def testSimpleQueryString(self):
    q = corpus_query.CorpusQuery.FromString('')
    self.assertEquals(q.AsQueryString(), '')

    (gql, args) = q.AsGQLWhereClause()
    self.assertEquals(gql, '')
    self.assertEquals(args, [])

  def testSimpleOpQueryString(self):
    q = corpus_query.CorpusQuery.FromString('a = 3')
    self.assertEquals(q.AsQueryString(), 'a = 3')

    (gql, args) = q.AsGQLWhereClause()
    self.assertEquals(gql, 'WHERE a = :1')
    self.assertEquals(args[0], 3)

  def testMultipleFiltersOpQueryString(self):
    q = corpus_query.CorpusQuery.FromString(
        'a = 3 AND b = 4')
    self.assertEquals(q.AsQueryString(), 'a = 3 AND b = 4')

    (gql, args) = q.AsGQLWhereClause()
    self.assertEquals(gql, 'WHERE a = :1 AND b = :2')
    self.assertEquals(args[0], 3)
    self.assertEquals(args[1], 4)

  def testDateRangeQueryString(self):
    q = corpus_query.CorpusQuery.FromString(
        'date >= Date(2015-01-01 00:00:00.00) AND ' +
        'date < Date(2015-02-01 00:00:00.00)')
    self.assertEquals(q.AsQueryString(),
        'date >= Date(2015-01-01 00:00:00.000000) AND '
        'date < Date(2015-02-01 00:00:00.000000)')

    (gql, args) = q.AsGQLWhereClause()
    self.assertEquals(gql, "WHERE date >= :1 AND date < :2")
    self.assertEquals(args[0], datetime.datetime(2015, 01, 01, 0, 0, 0))
    self.assertEquals(args[1], datetime.datetime(2015, 02, 01, 0, 0, 0))

  def testSimpleOpWithMaxTraceHandlesQueryString(self):
    q = corpus_query.CorpusQuery.FromString('a = 3 AND MAX_TRACE_HANDLES=3')
    self.assertEquals(q.AsQueryString(), 'a = 3 AND MAX_TRACE_HANDLES=3')

    (gql, args) = q.AsGQLWhereClause()
    self.assertEquals(gql, 'WHERE a = :1 LIMIT 3')
    self.assertEquals(args[0], 3)

  def testMixedTupleQueryString(self):
    q = corpus_query.CorpusQuery.FromString("a IN ('a', 'b', 3, 'c')")
    self.assertEquals(q.AsQueryString(), "a IN ('a', 'b', 3, 'c')")

    (gql, args) = q.AsGQLWhereClause()
    self.assertEquals(gql, "WHERE a IN :1")
    self.assertEquals(args[0], ('a', 'b', 3, 'c'))

  def testMaxTraceHandlesQueryString(self):
    q = corpus_query.CorpusQuery.FromString("MAX_TRACE_HANDLES=1")
    self.assertEquals(q.AsQueryString(), "MAX_TRACE_HANDLES=1")

    (gql, args) = q.AsGQLWhereClause()
    self.assertEquals(gql, "LIMIT 1")
    self.assertEquals(args, [])
