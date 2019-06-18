# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import story
from telemetry import page as page_module
from telemetry import value


class TestBase(unittest.TestCase):
  def setUp(self):
    story_set = story.StorySet(base_dir=os.path.dirname(__file__))
    story_set.AddStory(
        page_module.Page("http://www.bar.com/", story_set, story_set.base_dir,
                         name='http://www.bar.com/'))
    story_set.AddStory(
        page_module.Page("http://www.baz.com/", story_set, story_set.base_dir,
                         name='http://www.baz.com/'))
    story_set.AddStory(
        page_module.Page("http://www.foo.com/", story_set, story_set.base_dir,
                         name='http://www.foo.com/'))
    self.story_set = story_set

  @property
  def pages(self):
    return self.story_set.stories

class ValueForTest(value.Value):
  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    pass

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values):
    pass

  @staticmethod
  def GetJSONTypeName():
    pass

class ValueForAsDictTest(ValueForTest):
  @staticmethod
  def GetJSONTypeName():
    return 'baz'


class ValueTest(TestBase):
  def testCompat(self):
    page0 = self.pages[0]
    page1 = self.pages[0]

    a = value.Value(page0, 'x', 'unit', important=False, description=None)
    b = value.Value(page1, 'x', 'unit', important=False, description=None)
    self.assertTrue(b.IsMergableWith(a))

    a = value.Value(page0, 'x', 'unit', important=False, description=None)
    b = value.Value(page0, 'x', 'unit', important=False, description=None)
    self.assertTrue(b.IsMergableWith(a))

  def testIncompat(self):
    page0 = self.pages[0]

    a = value.Value(page0, 'x', 'unit', important=False, description=None)
    b = value.Value(page0, 'x', 'incompatUnit', important=False,
                    description=None)
    self.assertFalse(b.IsMergableWith(a))

    a = value.Value(page0, 'x', 'unit', important=False, description=None)
    b = value.Value(page0, 'x', 'unit', important=True, description=None)
    self.assertFalse(b.IsMergableWith(a))

    a = value.Value(page0, 'x', 'unit', important=False, description=None)
    c = ValueForTest(page0, 'x', 'unit', important=True, description=None)
    self.assertFalse(c.IsMergableWith(a))

  def testNameMustBeString(self):
    with self.assertRaises(ValueError):
      value.Value(None, 42, 'unit', important=False, description=None)

  def testUnitsMustBeString(self):
    with self.assertRaises(ValueError):
      value.Value(None, 'x', 42, important=False, description=None)

  def testImportantMustBeBool(self):
    with self.assertRaises(ValueError):
      value.Value(None, 'x', 'unit', important='foo', description=None)

  def testDescriptionMustBeStringOrNone(self):
    with self.assertRaises(ValueError):
      value.Value(None, 'x', 'unit', important=False, description=42)

  def testAsDictBaseKeys(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=True, description=None)
    d = v.AsDict()

    self.assertEquals(d, {
        'name': 'x',
        'type': 'baz',
        'units': 'unit',
        'important': True,
    })

  def testAsDictWithPage(self):
    page0 = self.pages[0]

    v = ValueForAsDictTest(page0, 'x', 'unit', important=False,
                           description=None)
    d = v.AsDict()

    self.assertIn('page_id', d)

  def testAsDictWithoutPage(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=False, description=None)
    d = v.AsDict()

    self.assertNotIn('page_id', d)

  def testAsDictWithDescription(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=False,
                           description='Some description.')
    d = v.AsDict()
    self.assertEqual('Some description.', d['description'])

  def testAsDictWithoutDescription(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=False, description=None)
    self.assertNotIn('description', v.AsDict())

  def testAsDictWithGroupingLabel(self):
    page = self.pages[0]
    page.grouping_keys['label'] = 'foo'
    v = ValueForAsDictTest(page, 'x', 'unit', important=False,
                           description='Some description.')
    d = v.AsDict()
    self.assertEqual('foo', d['tir_label'])

  def testAsDictWithoutGroupingLabel(self):
    page = self.pages[0]
    v = ValueForAsDictTest(page, 'x', 'unit', important=False, description=None)
    self.assertNotIn('tir_label', v.AsDict())
