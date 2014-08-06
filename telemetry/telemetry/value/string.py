# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import value as value_module
from telemetry.value import list_of_string_values

class StringValue(value_module.Value):
  def __init__(self, page, name, units, value, important=True,
               description=None):
    """A single value (float, integer or string) result from a test.

    A test that output a hash of the content in a page might produce a
    string value:
       StringValue(page, 'page_hash', 'hash', '74E377FF')
    """
    super(StringValue, self).__init__(page, name, units, important, description)
    assert isinstance(value, basestring)
    self.value = value

  def __repr__(self):
    if self.page:
      page_name = self.page.url
    else:
      page_name = None
    return 'StringValue(%s, %s, %s, %s, important=%s, description=%s)' % (
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

  @staticmethod
  def GetJSONTypeName():
    return 'string'

  def AsDict(self):
    d = super(StringValue, self).AsDict()
    d['value'] = self.value
    return d

  @staticmethod
  def FromDict(value_dict, page_dict):
    kwargs = value_module.Value.GetConstructorKwArgs(value_dict, page_dict)
    kwargs['value'] = value_dict['value']

    return StringValue(**kwargs)

  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    assert len(values) > 0
    v0 = values[0]
    return list_of_string_values.ListOfStringValues(
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
    return list_of_string_values.ListOfStringValues(
        None, name, v0.units,
        [v.value for v in values],
        important=v0.important)
