# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import webapp2
import webtest

from dashboard import edit_config_handler
from dashboard import put_entities_task
from dashboard import request_handler
from dashboard import testing_common
from dashboard.models import graph_data


class EditConfigHandlerTest(testing_common.TestCase):

  # TODO(qyearsley): Add a simple helper class and separate tests for
  # EditConfigHandler.

  def setUp(self):
    super(EditConfigHandlerTest, self).setUp()
    app = webapp2.WSGIApplication([
        ('/put_entities_task', put_entities_task.PutEntitiesTaskHandler)])
    self.testapp = webtest.TestApp(app)
    self.SetCurrentUser('foo@bar.com', is_admin=True)

  def _AddSampleTestData(self):
    """Adds some sample data used in the tests below."""
    master = graph_data.Master(id='TheMaster').put()
    graph_data.Bot(id='TheBot', parent=master).put()
    graph_data.TestMetadata(id='TheMaster/TheBot/Suite1').put()
    graph_data.TestMetadata(id='TheMaster/TheBot/Suite2').put()
    graph_data.TestMetadata(
        id='TheMaster/TheBot/Suite1/aaa', has_rows=True).put()
    graph_data.TestMetadata(
        id='TheMaster/TheBot/Suite1/bbb', has_rows=True).put()
    graph_data.TestMetadata(
        id='TheMaster/TheBot/Suite2/ccc', has_rows=True).put()
    graph_data.TestMetadata(
        id='TheMaster/TheBot/Suite2/ddd', has_rows=True).put()

  def testSplitPatternLines_OnePattern(self):
    # The SplitPatternLines function returns a list of patterns.
    self.assertEqual([], edit_config_handler._SplitPatternLines(''))
    self.assertEqual(['A/b/c'], edit_config_handler._SplitPatternLines('A/b/c'))
    self.assertEqual(
        ['A/b/c'], edit_config_handler._SplitPatternLines('A/b/c\n\n'))

  def testSplitPatternLines_SortsPatterns(self):
    # Re-ordering and extra newlines are ignored in patterns input.
    self.assertEqual(
        ['A/b/c/d', 'E/f/g/h'],
        edit_config_handler._SplitPatternLines('A/b/c/d\nE/f/g/h'))
    self.assertEqual(
        ['A/b/c/d', 'E/f/g/h'],
        edit_config_handler._SplitPatternLines('E/f/g/h\nA/b/c/d'))
    self.assertEqual(
        ['A/b/c/d', 'E/f/g/h'],
        edit_config_handler._SplitPatternLines('A/b/c/d\n\nE/f/g/h\n'))

  def testSplitPatternLines_NoSlashes_RaisesError(self):
    # A valid test path must contain a master, bot, and test part.
    with self.assertRaises(request_handler.InvalidInputError):
      edit_config_handler._SplitPatternLines('invalid')

  def testSplitPatternLines_HasBrackets_RaisesError(self):
    # Strings with brackets in them cannot be valid test paths.
    with self.assertRaises(request_handler.InvalidInputError):
      edit_config_handler._SplitPatternLines('A/b/c/d/[e]')

  def testChangeTestPatterns_NoneValue_RaisesTypeError(self):
    with self.assertRaises(TypeError):
      edit_config_handler._ChangeTestPatterns('a/b/c', None)

  def testChangeTestPatterns_NoChange_ReturnsEmptySets(self):
    self.assertEqual(
        (set(), set()),
        edit_config_handler._ChangeTestPatterns([], []))
    self.assertEqual(
        (set(), set()),
        edit_config_handler._ChangeTestPatterns(['a/b/c'], ['a/b/c']))

  def testChangeTestPatterns_OnlyAdd_ReturnsAddedAndEmptySet(self):
    self._AddSampleTestData()
    self.assertEqual(
        ({'TheMaster/TheBot/Suite1/aaa'}, set()),
        edit_config_handler._ChangeTestPatterns(
            ['*/*/*/bbb'], ['*/*/*/aaa', '*/*/*/bbb']))

  def testChangeTestPatterns_OnlyRemove_ReturnsEmptySetAndRemoved(self):
    self._AddSampleTestData()
    self.assertEqual(
        (set(), {'TheMaster/TheBot/Suite1/bbb'}),
        edit_config_handler._ChangeTestPatterns(
            ['*/*/*/aaa', '*/*/Suite1/bbb'], ['*/*/*/aaa']))

  def testChangeTestPatterns_RemoveAndAdd_ReturnsAddedAndRemoved(self):
    self._AddSampleTestData()
    added = {
        'TheMaster/TheBot/Suite1/aaa',
    }
    removed = {
        'TheMaster/TheBot/Suite2/ccc',
        'TheMaster/TheBot/Suite2/ddd',
    }
    self.assertEqual(
        (added, removed),
        edit_config_handler._ChangeTestPatterns(
            ['*/*/Suite2/*'], ['*/*/*/aaa']))

  def testChangeTestPatterns_CanTakeSetsAsArguments(self):
    self._AddSampleTestData()
    self.assertEqual(
        ({'TheMaster/TheBot/Suite1/aaa'}, set()),
        edit_config_handler._ChangeTestPatterns(set(), {'*/*/Suite1/aaa'}))

  def testComputeDeltas_Empty(self):
    self.assertEqual((set(), set()), edit_config_handler._ComputeDeltas([], []))

  def testComputeDeltas_OnlyAdded(self):
    self.assertEqual(
        ({'a'}, set()), edit_config_handler._ComputeDeltas('bcd', 'abcd'))

  def testComputeDeltas_OnlyRemoved(self):
    self.assertEqual(
        (set(), {'a'}), edit_config_handler._ComputeDeltas('abcd', 'bcd'))

  def testRemoveOverlapping_NoOverlap_ReturnsSameSet(self):
    self.assertEqual(
        ({1, 2, 3}, {4, 5, 6}),
        edit_config_handler._RemoveOverlapping({1, 2, 3}, {4, 5, 6}))

  def testRemoveOverlapping_SomeOverlap_ReturnsSetDifferences(self):
    self.assertEqual(
        ({1}, {3}), edit_config_handler._RemoveOverlapping({1, 2}, {2, 3}))

  def testRemoveOverlapping_AllOverlap_ReturnsEmptySets(self):
    self.assertEqual(
        (set(), set()), edit_config_handler._RemoveOverlapping({1, 2}, {1, 2}))


if __name__ == '__main__':
  unittest.main()
