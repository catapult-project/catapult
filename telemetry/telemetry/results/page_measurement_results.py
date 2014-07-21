# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.results import page_test_results
from telemetry.value import failure

class PageMeasurementResults(page_test_results.PageTestResults):
  def __init__(self, output_stream=None, trace_tag=''):
    super(PageMeasurementResults, self).__init__(output_stream)
    self._trace_tag = trace_tag

    self._current_page = None
    self._page_specific_values_for_current_page = None

  @property
  def current_page(self):
    return self._current_page

  @property
  def page_specific_values_for_current_page(self):
    assert self._current_page
    return self._page_specific_values_for_current_page

  def WillMeasurePage(self, page):
    assert not self._current_page
    self._current_page = page
    self._page_specific_values_for_current_page = []

  def AddValue(self, value):
    super(PageMeasurementResults, self).AddValue(value)
    if not isinstance(value, failure.FailureValue):
      self._page_specific_values_for_current_page.append(value)

  def DidMeasurePage(self):
    assert self._current_page, 'Failed to call WillMeasurePage'
    self._current_page = None
    self._page_specific_values_for_current_page = None
