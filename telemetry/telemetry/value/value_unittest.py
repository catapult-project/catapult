# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest

from telemetry import page as page_module
from telemetry import value
from telemetry.page import page_set


class TestBase(unittest.TestCase):
  def setUp(self):
    ps = page_set.PageSet(file_path=os.path.dirname(__file__))
    ps.AddUserStory(page_module.Page("http://www.bar.com/", ps, ps.base_dir))
    ps.AddUserStory(page_module.Page("http://www.baz.com/", ps, ps.base_dir))
    ps.AddUserStory(page_module.Page("http://www.foo.com/", ps, ps.base_dir))
    self.page_set = ps

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

  def GetChartAndTraceNameForComputedSummaryResult(
      self, trace_tag):
    pass

  def GetRepresentativeNumber(self):
    pass

  def GetRepresentativeString(self):
    pass

  @staticmethod
  def GetJSONTypeName():
    pass

class ValueForAsDictTest(ValueForTest):
  @staticmethod
  def GetJSONTypeName():
    return 'baz'

class ValueForFromDictTest(ValueForTest):
  @staticmethod
  def FromDict(value_dict, page_dict):
    kwargs = value.Value.GetConstructorKwArgs(value_dict, page_dict)
    return ValueForFromDictTest(**kwargs)

  @staticmethod
  def GetJSONTypeName():
    return 'value_for_from_dict_test'

class ValueTest(TestBase):
  def testCompat(self):
    page0 = self.pages[0]
    page1 = self.pages[0]

    a = value.Value(page0, 'x', 'unit', important=False, description=None,
                    interaction_record='foo')
    b = value.Value(page1, 'x', 'unit', important=False, description=None,
                    interaction_record='foo')
    self.assertTrue(b.IsMergableWith(a))

  def testIncompat(self):
    page0 = self.pages[0]

    a = value.Value(page0, 'x', 'unit', important=False, description=None,
                    interaction_record=None)
    b = value.Value(page0, 'x', 'incompatUnit', important=False,
                    interaction_record=None, description=None)
    self.assertFalse(b.IsMergableWith(a))

    a = value.Value(page0, 'x', 'unit', important=False, description=None,
                    interaction_record=None)
    b = value.Value(page0, 'x', 'unit', important=True, description=None,
                    interaction_record=None)
    self.assertFalse(b.IsMergableWith(a))

    a = value.Value(page0, 'x', 'unit', important=False, description=None,
                    interaction_record=None)
    b = ValueForTest(page0, 'x', 'unit', important=True, description=None,
                     interaction_record=None)
    self.assertFalse(b.IsMergableWith(a))

    a = value.Value(page0, 'x', 'unit', important=False, description=None,
                    interaction_record='foo')
    b = value.Value(page0, 'x', 'unit', important=False, description=None,
                     interaction_record='bar')
    self.assertFalse(b.IsMergableWith(a))

  def testNameMustBeString(self):
    with self.assertRaises(ValueError):
      value.Value(None, 42, 'unit', important=False, description=None,
                  interaction_record=None)

  def testUnitsMustBeString(self):
    with self.assertRaises(ValueError):
      value.Value(None, 'x', 42, important=False, description=None,
                  interaction_record=None)

  def testImportantMustBeBool(self):
    with self.assertRaises(ValueError):
      value.Value(None, 'x', 'unit', important='foo', description=None,
                  interaction_record=None)

  def testDescriptionMustBeStringOrNone(self):
    with self.assertRaises(ValueError):
      value.Value(None, 'x', 'unit', important=False, description=42,
                  interaction_record=None)

  def testInteractionRecordMustBeStringOrNone(self):
    with self.assertRaises(ValueError):
      value.Value(None, 'x', 'unit', important=False, description=None,
                  interaction_record=42)

  def testAsDictBaseKeys(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=True, description=None,
                           interaction_record='bar')
    d = v.AsDict()

    self.assertEquals(d, {
          'name': 'x',
          'type': 'baz',
          'units': 'unit',
          'important': True,
          'interaction_record': 'bar'
        })

  def testAsDictWithPage(self):
    page0 = self.pages[0]

    v = ValueForAsDictTest(page0, 'x', 'unit', important=False,
                           description=None, interaction_record=None)
    d = v.AsDict()

    self.assertIn('page_id', d)

  def testAsDictWithoutPage(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=False, description=None,
                           interaction_record=None)
    d = v.AsDict()

    self.assertNotIn('page_id', d)

  def testAsDictWithDescription(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=False,
                           description='Some description.',
                           interaction_record=None)
    d = v.AsDict()
    self.assertEqual('Some description.', d['description'])

  def testAsDictWithoutDescription(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=False, description=None,
                           interaction_record=None)
    self.assertNotIn('description', v.AsDict())

  def testAsDictWithInteractionRecord(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=False,
                           description='Some description.',
                           interaction_record='foo')
    d = v.AsDict()
    self.assertEqual('foo', d['interaction_record'])

  def testAsDictWithoutDescription(self):
    v = ValueForAsDictTest(None, 'x', 'unit', important=False, description=None,
                           interaction_record=None)
    self.assertNotIn('interaction_record', v.AsDict())

  def testFromDictBaseKeys(self):
    d = {
      'type': 'value_for_from_dict_test',
      'name': 'x',
      'units': 'unit'
    }

    v = value.Value.FromDict(d, None)
    self.assertEquals(v.name, 'x')
    self.assertTrue(isinstance(v, ValueForFromDictTest))
    self.assertEquals(v.units, 'unit')

  def testFromDictWithPage(self):
    page0 = self.pages[0]
    page_dict = {page0.id: page0}

    d = {
      'type': 'value_for_from_dict_test',
      'name': 'x',
      'units': 'unit',
      'page_id': page0.id
    }

    v = value.Value.FromDict(d, page_dict)

    self.assertEquals(v.page.id, page0.id)

  def testFromDictWithoutPage(self):
    d = {
      'type': 'value_for_from_dict_test',
      'name': 'x',
      'units': 'unit'
    }

    v = value.Value.FromDict(d, {})

    self.assertEquals(v.page, None)

  def testFromDictWithDescription(self):
    d = {
          'type': 'value_for_from_dict_test',
          'name': 'x',
          'units': 'unit',
          'description': 'foo'
        }

    v = value.Value.FromDict(d, {})
    self.assertEquals(v.description, 'foo')

  def testFromDictWithoutDescription(self):
    d = {
          'type': 'value_for_from_dict_test',
          'name': 'x',
          'units': 'unit'
        }

    v = value.Value.FromDict(d, {})
    self.assertEquals(v.description, None)

  def testFromDictWithInteractionRecord(self):
    d = {
          'type': 'value_for_from_dict_test',
          'name': 'x',
          'units': 'unit',
          'description': 'foo',
          'interaction_record': 'bar'
        }

    v = value.Value.FromDict(d, {})
    self.assertEquals(v.interaction_record, 'bar')

  def testFromDictWithoutInteractionRecord(self):
    d = {
          'type': 'value_for_from_dict_test',
          'name': 'x',
          'units': 'unit'
        }

    v = value.Value.FromDict(d, {})
    self.assertEquals(v.interaction_record, None)

  def testListOfValuesFromListOfDicts(self):
    d0 = {
          'type': 'value_for_from_dict_test',
          'name': 'x',
          'units': 'unit'
        }
    d1 = {
          'type': 'value_for_from_dict_test',
          'name': 'y',
          'units': 'unit'
        }
    vs = value.Value.ListOfValuesFromListOfDicts([d0, d1], {})
    self.assertEquals(vs[0].name, 'x')
    self.assertEquals(vs[1].name, 'y')
