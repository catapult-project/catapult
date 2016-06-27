# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry import decorators
from telemetry.timeline import chrome_trace_category_filter


@decorators.Deprecated(2016, 6, 27, 'This function is deprecated. Please use '
                       'the one in chrome_trace_category_filter.')
def CreateNoOverheadFilter():
  return chrome_trace_category_filter.CreateNoOverheadFilter()


@decorators.Deprecated(2016, 6, 27, 'This function is deprecated. Please use '
                       'the one in chrome_trace_category_filter.')
def CreateMinimalOverheadFilter():
  return chrome_trace_category_filter.CreateMinimalOverheadFilter()


@decorators.Deprecated(2016, 6, 27, 'This function is deprecated. Please use '
                       'the one in chrome_trace_category_filter.')
def CreateDebugOverheadFilter():
  return chrome_trace_category_filter.CreateDebugOverheadFilter()


@decorators.Deprecated(2016, 6, 27, 'This class is deprecated. Please use '
                       'the one in chrome_trace_category_filter.')
class TracingCategoryFilter(
    chrome_trace_category_filter.ChromeTraceCategoryFilter):

  def __init__(self, filter_string=None):
    super(TracingCategoryFilter, self).__init__(filter_string)
