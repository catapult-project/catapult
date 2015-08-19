# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for utils module."""

import unittest

from google.appengine.ext import ndb

from dashboard import testing_common
from dashboard import utils
from dashboard.models import graph_data


class UtilsTest(testing_common.TestCase):

  def setUp(self):
    super(UtilsTest, self).setUp()
    testing_common.SetInternalDomain('google.com')

  def _AssertMatches(self, test_path, pattern):
    """Asserts that a test path matches a pattern with MatchesPattern."""
    test_key = utils.TestKey(test_path)
    self.assertTrue(utils.TestMatchesPattern(test_key, pattern))

  def _AssertDoesntMatch(self, test_path, pattern):
    """Asserts that a test path doesn't match a pattern with MatchesPattern."""
    test_key = utils.TestKey(test_path)
    self.assertFalse(utils.TestMatchesPattern(test_key, pattern))

  def testMatchesPattern_AllWildcards(self):
    self._AssertMatches(
        'ChromiumPerf/cros-one/dromaeo.top25/Total', '*/*/*/*')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total', '*/*/*')

  def testMatchesPattern_SomeWildcards(self):
    self._AssertMatches(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/*/dromaeo.top25/*')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/*/dromaeo.another_page_set/*')

  def testMatchesPattern_SomePartialWildcards(self):
    self._AssertMatches(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/cros-*/dromaeo.*/Total')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeoXtop25/Total',
        'ChromiumPerf/cros-*/dromaeo.*/Total')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'OtherMaster/cros-*/dromaeo.*/Total')

  def testMatchesPattern_MorePartialWildcards(self):
    # Note that the wildcard matches zero or more characters.
    self._AssertMatches(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'Chromium*/cros-one*/*.*/To*al')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'Chromium*/linux-*/*.*/To*al')

  def testMatchesPattern_RequiresFullMatchAtEnd(self):
    # If there is no wildcard at the beginning or end of the
    # test path part, then a part will only match if it matches
    # right up to the beginning or end.
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/cros-one/dromaeo.top25/*Tot')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/cros-one/dromaeo.top25/otal*')

  def _PutEntitiesAllExternal(self):
    """Puts entities (none internal-only) and returns the keys."""
    master = graph_data.Master(id='M').put()
    bot = graph_data.Bot(parent=master, id='b').put()
    keys = [
        graph_data.Test(id='a', parent=bot, internal_only=False).put(),
        graph_data.Test(id='b', parent=bot, internal_only=False).put(),
        graph_data.Test(id='c', parent=bot, internal_only=False).put(),
        graph_data.Test(id='d', parent=bot, internal_only=False).put(),
    ]
    return keys

  def _PutEntitiesHalfInternal(self):
    """Puts entities (half internal-only) and returns the keys."""
    master = graph_data.Master(id='M').put()
    bot = graph_data.Bot(parent=master, id='b').put()
    keys = [
        graph_data.Test(id='ax', parent=bot, internal_only=True).put(),
        graph_data.Test(id='a', parent=bot, internal_only=False).put(),
        graph_data.Test(id='b', parent=bot, internal_only=False).put(),
        graph_data.Test(id='bx', parent=bot, internal_only=True).put(),
        graph_data.Test(id='c', parent=bot, internal_only=False).put(),
        graph_data.Test(id='cx', parent=bot, internal_only=True).put(),
        graph_data.Test(id='d', parent=bot, internal_only=False).put(),
        graph_data.Test(id='dx', parent=bot, internal_only=True).put(),
    ]
    return keys

  def testGetMulti_NotLoggedIn_OnlySome(self):
    """Tests that GetMulti gets some of the entities when not logged in."""
    keys = self._PutEntitiesHalfInternal()
    self.SetCurrentUser('x@hotmail.com')
    self.assertEqual(len(keys) / 2, len(utils.GetMulti(keys)))

  def testGetMulti_LoggedIn(self):
    """Tests that GetMulti gets all of the entities when logged in."""
    keys = self._PutEntitiesHalfInternal()
    self.SetCurrentUser('x@google.com')
    self.assertEqual(len(keys), len(utils.GetMulti(keys)))

  def testGetMulti_AllExternal(self):
    """Tests that GetMulti gets all of the entities when logged in."""
    keys = self._PutEntitiesAllExternal()
    self.SetCurrentUser('x@hotmail.com')
    self.assertEqual(len(keys), len(utils.GetMulti(keys)))

  def testTestSuiteName_Basic(self):
    key = utils.TestKey('Master/bot/suite-foo/sub/x/y/z')
    self.assertEqual('suite-foo', utils.TestSuiteName(key))

  def testTestSuiteName_KeyNotLongEnough_ReturnsNone(self):
    key = ndb.Key('Master', 'M', 'Bot', 'b')
    self.assertIsNone(utils.TestSuiteName(key))

  def testMinimumRange_Empty_ReturnsNone(self):
    self.assertIsNone(utils.MinimumRange([]))

  def testMinimumRange_NotOverlapping_ReturnsNone(self):
    self.assertIsNone(utils.MinimumRange([(5, 10), (15, 20)]))

  def testMinimumRange_OneRange_ReturnsSameRange(self):
    self.assertEqual((5, 10), utils.MinimumRange([(5, 10)]))

  def testMinimumRange_OverlapsForOneNumber_ReturnsRangeWithOneNumber(self):
    self.assertEqual((5, 5), utils.MinimumRange([(2, 5), (5, 10)]))

  def testMinimumRange_MoreThanTwoRanges_ReturnsIntersection(self):
    self.assertEqual((6, 14), utils.MinimumRange(
        [(3, 20), (5, 15), (6, 25), (3, 14)]))


if __name__ == '__main__':
  unittest.main()
