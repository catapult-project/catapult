# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from tracing.value import histogram_unittest
from tracing.value.diagnostics import diagnostic
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import tag_map

def _SortStories(d):
  for story_names in d['tagsToStoryNames'].values():
    story_names.sort()
  return d


class TagMapUnittest(unittest.TestCase):

  def testEquality(self):
    tags0 = {
        'tag1': ['path1', 'path2'],
        'tag2': ['path1', 'path2', 'path3']
    }
    tags1 = {
        'tag1': ['path1', 'path2'],
        'tag2': ['path1', 'path2', 'path3']
    }
    info0 = tag_map.TagMap({'tagsToStoryNames': tags0})
    info1 = tag_map.TagMap({'tagsToStoryNames': tags1})
    self.assertEqual(info0, info1)

  def testInequality(self):
    tags0 = {
        'tag1': ['path1', 'path2'],
        'tag2': ['path1', 'path2', 'path3']
    }
    tags1 = {
        'tag1': ['path1', 'path2']
    }
    info0 = tag_map.TagMap({'tagsToStoryNames': tags0})
    info1 = tag_map.TagMap({'tagsToStoryNames': tags1})
    self.assertNotEqual(info0, info1)

  def testRoundtrip(self):
    tags = {
        'tag1': ['path1', 'path2', 'path3'],
        'tag2': ['path1', 'path4'],
        'tag3': ['path5'],
    }
    info = tag_map.TagMap({'tagsToStoryNames': tags})
    d = info.AsDict()
    clone = diagnostic.Diagnostic.FromDict(d)
    self.assertEqual(histogram_unittest.ToJSON(_SortStories(d)),
                     histogram_unittest.ToJSON(_SortStories(clone.AsDict())))
    self.assertSetEqual(
        clone.tags_to_story_names['tag1'], set(tags['tag1']))
    self.assertSetEqual(
        clone.tags_to_story_names['tag2'], set(tags['tag2']))
    self.assertSetEqual(
        clone.tags_to_story_names['tag3'], set(tags['tag3']))

  def AddTagAndStoryDisplayName(self):
    tagmap = tag_map.TagMap({})
    self.assertDictEqual({}, tagmap.tags_to_story_names)

    tagmap.AddTagAndStoryDisplayName('foo', 'bar')
    self.assertListEqual(['foo'], tagmap.tags_to_story_names.keys())
    self.assertSetEqual(set(['bar']), tagmap.tags_to_story_names['foo'])

    tagmap.AddTagAndStoryDisplayName('foo', 'bar2')
    self.assertListEqual(['foo'], tagmap.tags_to_story_names.keys())
    self.assertSetEqual(
        set(['bar', 'bar2']), tagmap.tags_to_story_names['foo'])

  def testMerge(self):
    t0 = tag_map.TagMap({
        'tagsToStoryNames': {
            'press': ['story0', 'story1'],
            'desktop': ['story0', 'story1', 'story2']
        }})

    t1 = tag_map.TagMap({
        'tagsToStoryNames': {
            'press': ['story3', 'story4'],
            'android': ['story3', 'story4', 'story5']
        }})

    self.assertFalse(t0.CanAddDiagnostic(generic_set.GenericSet([])))
    self.assertTrue(t0.CanAddDiagnostic(t1))

    m0 = diagnostic.Diagnostic.FromDict(t0.AsDict())

    self.assertTrue(isinstance(m0, tag_map.TagMap))
    self.assertFalse(
        m0.CanAddDiagnostic(generic_set.GenericSet([])))
    self.assertTrue(m0.CanAddDiagnostic(t1))

    m0.AddDiagnostic(t1)

    m1 = diagnostic.Diagnostic.FromDict(t1.AsDict())
    m1.AddDiagnostic(t0)

    self.assertDictEqual(_SortStories(m0.AsDict()), _SortStories(m1.AsDict()))

    m2 = diagnostic.Diagnostic.FromDict(t1.AsDict())

    self.assertNotEqual(_SortStories(m2.AsDict()), _SortStories(m0.AsDict()))

    # Test round-tripping of merged diagnostic
    clone = diagnostic.Diagnostic.FromDict(m0.AsDict())

    self.assertSetEqual(
        set(clone.tags_to_story_names.keys()),
        set(['press', 'desktop', 'android']))
    self.assertSetEqual(
        clone.tags_to_story_names.get('press'),
        set(['story0', 'story1', 'story3', 'story4']))
    self.assertSetEqual(
        clone.tags_to_story_names.get('desktop'),
        set(['story0', 'story1', 'story2']))
    self.assertSetEqual(
        clone.tags_to_story_names.get('android'),
        set(['story3', 'story4', 'story5']))
