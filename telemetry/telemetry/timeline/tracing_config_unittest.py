# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_config
from telemetry.timeline import tracing_options


class TracingConfigTests(unittest.TestCase):
  def testDefault(self):
    options = tracing_options.TracingOptions()
    category_filter = tracing_category_filter.TracingCategoryFilter()
    config = tracing_config.TracingConfig(options, category_filter)
    config_string = config.GetTraceConfigJsonString()
    self.assertEquals(
        '{'
          '"record_mode": "record-as-much-as-possible"'
        '}',
        config_string)

  def testBasic(self):
    options = tracing_options.TracingOptions()
    options.record_mode = tracing_options.RECORD_UNTIL_FULL
    options.enable_systrace = True
    category_filter = tracing_category_filter.TracingCategoryFilter(
        'x,-y,disabled-by-default-z,DELAY(7;foo)')
    config = tracing_config.TracingConfig(options, category_filter)
    config_string = config.GetTraceConfigJsonString()
    self.assertEquals(
        '{'
          '"enable_systrace": true, '
          '"excluded_categories": ["y"], '
          '"included_categories": ["x", "disabled-by-default-z"], '
          '"record_mode": "record-until-full", '
          '"synthetic_delays": ["DELAY(7;foo)"]'
        '}',
        config_string)
