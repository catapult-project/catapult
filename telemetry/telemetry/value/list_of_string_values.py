# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import value as value_module

class ListOfStringValues(value_module.Value):
  def __init__(self, page, name, units, values,
               important=True, description=None,
               same_page_merge_policy=value_module.CONCATENATE):
    super(ListOfStringValues, self).__init__(page, name, units, important,
                                             description)
    assert len(values) > 0
    assert isinstance(values, list)
    for v in values:
      assert isinstance(v, basestring)
    self.values = values
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
    return ('ListOfStringValues(%s, %s, %s, %s, ' +
            'important=%s, description=%s, same_page_merge_policy=%s)') % (
              page_name,
              self.name,
              self.units,
              repr(self.values),
              self.important,
              self.description,
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
    return d

  @staticmethod
  def FromDict(value_dict, page_dict):
    kwargs = value_module.Value.GetConstructorKwArgs(value_dict, page_dict)
    kwargs['values'] = value_dict['values']

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
          same_page_merge_policy=v0.same_page_merge_policy)

    assert v0.same_page_merge_policy == value_module.CONCATENATE
    all_values = []
    for v in values:
      all_values.extend(v.values)
    return ListOfStringValues(
        v0.page, v0.name, v0.units,
        all_values,
        important=v0.important,
        same_page_merge_policy=v0.same_page_merge_policy)

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values,
                                        group_by_name_suffix=False):
    assert len(values) > 0
    v0 = values[0]
    all_values = []
    for v in values:
      all_values.extend(v.values)
    if not group_by_name_suffix:
      name = v0.name
    else:
      name = v0.name_suffix
    return ListOfStringValues(
        None, name, v0.units,
        all_values,
        important=v0.important,
        same_page_merge_policy=v0.same_page_merge_policy)
