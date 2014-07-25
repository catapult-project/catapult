# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import numbers

from telemetry import value as value_module
from telemetry.value import list_of_scalar_values

class ScalarValue(value_module.Value):
  def __init__(self, page, name, units, value, important=True,
               description=None):
    """A single value (float or integer) result from a test.

    A test that counts the number of DOM elements in a page might produce a
    scalar value:
       ScalarValue(page, 'num_dom_elements', 'count', num_elements)
    """
    super(ScalarValue, self).__init__(page, name, units, important, description)
    assert isinstance(value, numbers.Number)
    self.value = value

  def __repr__(self):
    if self.page:
      page_name = self.page.url
    else:
      page_name = None
    return 'ScalarValue(%s, %s, %s, %s, important=%s, description=%s)' % (
      page_name,
      self.name,
      self.units,
      self.value,
      self.important,
      self.description)

  def GetBuildbotDataType(self, output_context):
    if self._IsImportantGivenOutputIntent(output_context):
      return 'default'
    return 'unimportant'

  def GetBuildbotValue(self):
    # Buildbot's print_perf_results method likes to get lists for all values,
    # even when they are scalar, so list-ize the return value.
    return [self.value]

  def GetRepresentativeNumber(self):
    return self.value

  def GetRepresentativeString(self):
    return str(self.value)

  @classmethod
  def GetJSONTypeName(cls):
    return 'scalar'

  def AsDict(self):
    d = super(ScalarValue, self).AsDict()
    d['value'] = self.value
    return d

  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    assert len(values) > 0
    v0 = values[0]
    return list_of_scalar_values.ListOfScalarValues(
        v0.page, v0.name, v0.units,
        [v.value for v in values],
        important=v0.important)

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values,
                                        group_by_name_suffix=False):
    assert len(values) > 0
    v0 = values[0]
    if not group_by_name_suffix:
      name = v0.name
    else:
      name = v0.name_suffix
    return list_of_scalar_values.ListOfScalarValues(
        None, name, v0.units,
        [v.value for v in values],
        important=v0.important)
