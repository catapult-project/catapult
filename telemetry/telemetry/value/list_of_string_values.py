# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import value as value_module
from telemetry.value import none_values


class ListOfStringValues(value_module.Value):
  def __init__(self, page, name, units, values,
               important=True, description=None,
               tir_label=None, none_value_reason=None,
               same_page_merge_policy=value_module.CONCATENATE):
    super(ListOfStringValues, self).__init__(page, name, units, important,
                                             description, tir_label)
    if values is not None:
      assert isinstance(values, list)
      assert len(values) > 0
      assert all(isinstance(v, basestring) for v in values)
    none_values.ValidateNoneValueReason(values, none_value_reason)
    self.values = values
    self.none_value_reason = none_value_reason
    self.same_page_merge_policy = same_page_merge_policy

  def __repr__(self):
    if self.page:
      page_name = self.page.url
    else:
      page_name = None
    if self.same_page_merge_policy == value_module.CONCATENATE:
      merge_policy = 'CONCATENATE'
    else:
      merge_policy = 'PICK_FIRST'
    return ('ListOfStringValues(%s, %s, %s, %s, '
            'important=%s, description=%s, tir_label=%s, '
            'same_page_merge_policy=%s)') % (
                page_name,
                self.name,
                self.units,
                repr(self.values),
                self.important,
                self.description,
                self.tir_label,
                merge_policy)

  def GetBuildbotDataType(self, output_context):
    if self._IsImportantGivenOutputIntent(output_context):
      return 'default'
    return 'unimportant'

  def GetBuildbotValue(self):
    return self.values

  def GetRepresentativeNumber(self):
    return None

  def GetRepresentativeString(self):
    return repr(self.values)

  def IsMergableWith(self, that):
    return (super(ListOfStringValues, self).IsMergableWith(that) and
            self.same_page_merge_policy == that.same_page_merge_policy)

  @staticmethod
  def GetJSONTypeName():
    return 'list_of_string_values'

  def AsDict(self):
    d = super(ListOfStringValues, self).AsDict()
    d['values'] = self.values

    if self.none_value_reason is not None:
      d['none_value_reason'] = self.none_value_reason

    return d

  @staticmethod
  def FromDict(value_dict, page_dict):
    kwargs = value_module.Value.GetConstructorKwArgs(value_dict, page_dict)
    kwargs['values'] = value_dict['values']

    if 'none_value_reason' in value_dict:
      kwargs['none_value_reason'] = value_dict['none_value_reason']
    if 'tir_label' in value_dict:
      kwargs['tir_label'] = value_dict['tir_label']

    return ListOfStringValues(**kwargs)

  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    assert len(values) > 0
    v0 = values[0]

    if v0.same_page_merge_policy == value_module.PICK_FIRST:
      return ListOfStringValues(
          v0.page, v0.name, v0.units,
          values[0].values,
          important=v0.important,
          same_page_merge_policy=v0.same_page_merge_policy,
          none_value_reason=v0.none_value_reason)

    assert v0.same_page_merge_policy == value_module.CONCATENATE
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
    merged_values = []
    none_value_reason = None
    for v in values:
      if v.values is None:
        merged_values = None
        none_value_reason = none_values.MERGE_FAILURE_REASON
        break
      merged_values.extend(v.values)
    return ListOfStringValues(
        page, name, v0.units,
        merged_values,
        important=v0.important,
        tir_label=tir_label,
        same_page_merge_policy=v0.same_page_merge_policy,
        none_value_reason=none_value_reason)
