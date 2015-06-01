# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import value as value_module
from telemetry.value import list_of_string_values
from telemetry.value import none_values


class StringValue(value_module.Value):
  def __init__(self, page, name, units, value, important=True,
               description=None, tir_label=None,
               none_value_reason=None):
    """A single value (float, integer or string) result from a test.

    A test that output a hash of the content in a page might produce a
    string value:
       StringValue(page, 'page_hash', 'hash', '74E377FF')
    """
    super(StringValue, self).__init__(page, name, units, important, description,
                                      tir_label)
    assert value is None or isinstance(value, basestring)
    none_values.ValidateNoneValueReason(value, none_value_reason)
    self.value = value
    self.none_value_reason = none_value_reason

  def __repr__(self):
    if self.page:
      page_name = self.page.url
    else:
      page_name = None
    return ('StringValue(%s, %s, %s, %s, important=%s, description=%s, '
            'tir_label=%s)') % (
                page_name,
                self.name,
                self.units,
                self.value,
                self.important,
                self.description,
                self.tir_label)

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

    if self.none_value_reason is not None:
      d['none_value_reason'] = self.none_value_reason

    return d

  @staticmethod
  def FromDict(value_dict, page_dict):
    kwargs = value_module.Value.GetConstructorKwArgs(value_dict, page_dict)
    kwargs['value'] = value_dict['value']

    if 'none_value_reason' in value_dict:
      kwargs['none_value_reason'] = value_dict['none_value_reason']
    if 'tir_label' in value_dict:
      kwargs['tir_label'] = value_dict['tir_label']

    return StringValue(**kwargs)

  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    assert len(values) > 0
    v0 = values[0]
    return cls._MergeLikeValues(values, v0.page, v0.name, v0.tir_label)

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values,
                                        group_by_name_suffix=False):
    assert len(values) > 0
    v0 = values[0]
    name = v0.name_suffix if group_by_name_suffix else v0.name
    return cls._MergeLikeValues(values, None, name, v0.tir_label)

  @classmethod
  def _MergeLikeValues(cls, values, page, name, tir_label):
    v0 = values[0]
    merged_value = [v.value for v in values]
    none_value_reason = None
    if None in merged_value:
      merged_value = None
      none_value_reason = none_values.MERGE_FAILURE_REASON
    return list_of_string_values.ListOfStringValues(
        page, name, v0.units, merged_value, important=v0.important,
        tir_label=tir_label,
        none_value_reason=none_value_reason)
