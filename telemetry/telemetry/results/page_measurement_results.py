# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.results import page_test_results

class PageMeasurementResults(page_test_results.PageTestResults):
  def __init__(self, output_stream=None, trace_tag=''):
    super(PageMeasurementResults, self).__init__(output_stream, trace_tag)
    self._trace_tag = trace_tag
