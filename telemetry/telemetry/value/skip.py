# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import value as value_module


class SkipValue(value_module.Value):

  def __init__(self, page, reason, is_expected, description=None):
    """A value representing a skipped page.

    Args:
      page: The skipped page object.
      reason: The string reason the page was skipped.
    """
    super(SkipValue, self).__init__(page, 'skip', '', True, description, None,
                                    None)
    self._reason = reason
    self._is_expected = is_expected

  def __repr__(self):
    page_name = self.page.name
    return 'SkipValue(%s, %s, description=%s)' % (page_name, self._reason,
                                                  self.description)

  @property
  def reason(self):
    return self._reason

  @property
  def expected(self):
    return self._is_expected

  def GetChartAndTraceNameForPerPageResult(self):
    return None

  @staticmethod
  def GetJSONTypeName():
    return 'skip'

  def AsDict(self):
    d = super(SkipValue, self).AsDict()
    d['reason'] = self._reason
    d['is_expected'] = self._is_expected
    return d

  @staticmethod
  def FromDict(value_dict, page_dict):
    kwargs = value_module.Value.GetConstructorKwArgs(value_dict, page_dict)
    del kwargs['name']
    del kwargs['units']
    if 'important' in kwargs:
      del kwargs['important']
    kwargs['reason'] = value_dict['reason']
    kwargs['is_expected'] = value_dict['is_expected']
    if 'tir_label' in kwargs:
      del kwargs['tir_label']
    if 'grouping_keys' in kwargs:
      del kwargs['grouping_keys']

    return SkipValue(**kwargs)  # pylint: disable=unexpected-keyword-arg

  @classmethod
  def MergeLikeValuesFromSamePage(cls, values):
    assert False, 'Should not be called.'

  @classmethod
  def MergeLikeValuesFromDifferentPages(cls, values):
    assert False, 'Should not be called.'
