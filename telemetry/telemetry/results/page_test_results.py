# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import copy
import logging
import traceback

from telemetry import value as value_module
from telemetry.value import failure
from telemetry.value import skip

class PageTestResults(object):
  def __init__(self, output_stream=None, output_formatters=None, trace_tag=''):
    """
    Args:
      output_stream: The output stream to use to write test results.
      output_formatters: A list of output formatters. The output
          formatters are typically used to format the test results, such
          as CsvOutputFormatter, which output the test results as CSV.
      trace_tag: A string to append to the buildbot trace
      name. Currently only used for buildbot.
    """
    # TODO(chrishenry): Figure out if trace_tag is still necessary.

    super(PageTestResults, self).__init__()
    self._output_stream = output_stream
    self._output_formatters = (
        output_formatters if output_formatters is not None else [])
    self._trace_tag = trace_tag
    self._current_page = None

    # TODO(chrishenry,eakuefner): Remove self.successes once they can
    # be inferred.
    self.successes = []

    self._representative_value_for_each_value_name = {}
    self._all_page_specific_values = []
    self._all_summary_values = []

  def __copy__(self):
    cls = self.__class__
    result = cls.__new__(cls)
    for k, v in self.__dict__.items():
      if isinstance(v, collections.Container):
        v = copy.copy(v)
      setattr(result, k, v)
    return result

  @property
  def all_page_specific_values(self):
    return self._all_page_specific_values

  @property
  def all_summary_values(self):
    return self._all_summary_values

  @property
  def current_page(self):
    return self._current_page

  @property
  def pages_that_succeeded(self):
    """Returns the set of pages that succeeded."""
    pages = set(value.page for value in self._all_page_specific_values)
    pages.difference_update(self.pages_that_had_failures)
    return pages

  @property
  def pages_that_had_failures(self):
    """Returns the set of failed pages."""
    return set(v.page for v in self.failures)

  @property
  def failures(self):
    values = self._all_page_specific_values
    return [v for v in values if isinstance(v, failure.FailureValue)]

  @property
  def skipped_values(self):
    values = self._all_page_specific_values
    return [v for v in values if isinstance(v, skip.SkipValue)]

  def _GetStringFromExcInfo(self, err):
    return ''.join(traceback.format_exception(*err))

  def WillRunPage(self, page):
    self._current_page = page

  def DidRunPage(self, page):  # pylint: disable=W0613
    self._current_page = None

  def AddValue(self, value):
    self._ValidateValue(value)
    # TODO(eakuefner/chrishenry): Add only one skip per pagerun assert here
    self._all_page_specific_values.append(value)

  def AddSummaryValue(self, value):
    assert value.page is None
    self._ValidateValue(value)
    self._all_summary_values.append(value)

  def _ValidateValue(self, value):
    assert isinstance(value, value_module.Value)
    if value.name not in self._representative_value_for_each_value_name:
      self._representative_value_for_each_value_name[value.name] = value
    representative_value = self._representative_value_for_each_value_name[
        value.name]
    assert value.IsMergableWith(representative_value)

  def AddSuccess(self, page):
    self.successes.append(page)

  def PrintSummary(self):
    for output_formatter in self._output_formatters:
      output_formatter.Format(self)

    if self.failures:
      logging.error('Failed pages:\n%s', '\n'.join(
          p.display_name for p in self.pages_that_had_failures))

    if self.skipped_values:
      logging.warning('Skipped pages:\n%s', '\n'.join(
          v.page.display_name for v in self.skipped_values))

  def FindPageSpecificValuesForPage(self, page, value_name):
    values = []
    for value in self.all_page_specific_values:
      if value.page == page and value.name == value_name:
        values.append(value)
    return values

  def FindAllPageSpecificValuesNamed(self, value_name):
    values = []
    for value in self.all_page_specific_values:
      if value.name == value_name:
        values.append(value)
    return values
