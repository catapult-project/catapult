# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import value
from telemetry.page import page_set

class TestBase(unittest.TestCase):
  def setUp(self):
    self.page_set =  page_set.PageSet(file_path=os.path.dirname(__file__))
    self.page_set.AddPageWithDefaultRunNavigate("http://www.bar.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.baz.com/")
    self.page_set.AddPageWithDefaultRunNavigate("http://www.foo.com/")

  @property
  def pages(self):
    return self.page_set.pages

class ValueForTest(value.Value):
  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    pass

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values,
                                        group_by_name_suffix=False):
    pass

  def GetBuildbotDataType(self, output_context):
    pass

  def GetBuildbotValue(self):
    pass

  def GetBuildbotMeasurementAndTraceNameForComputedSummaryResult(
      self, trace_tag):
    pass

  def GetRepresentativeNumber(self):
    pass

  def GetRepresentativeString(self):
    pass

  @classmethod
  def GetJSONTypeName(cls):
    pass

class ValueForAsDictTest(ValueForTest):
  @classmethod
  def GetJSONTypeName(cls):
    return 'baz'

class ValueTest(TestBase):
  def testCompat(self):
    page0 = self.pages[0]
    page1 = self.pages[0]

    a = value.Value(page0, 'x', 'unit', important=False, description=None)
    b = value.Value(page1, 'x', 'unit', important=False, description=None)
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
    b = ValueForTest(page0, 'x', 'unit', important=True, description=None)
    self.assertFalse(b.IsMergableWith(a))

  def testAsDictBaseKeys(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=True, description=None)
    d = v.AsDict()

    self.assertEquals(d, {
          'name': 'x',
          'type': 'baz',
          'unit': 'unit',
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
