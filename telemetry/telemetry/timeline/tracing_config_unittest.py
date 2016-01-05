# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_config
from telemetry.timeline import tracing_options


class TracingConfigTests(unittest.TestCase):
  def testDefault(self):
    config = tracing_config.TracingConfig()
    config_string = config.GetChromeTraceConfigJsonString()
    self.assertEquals(
        '{'
          '"record_mode": "record-as-much-as-possible"'
        '}',
        config_string)

  def testBasic(self):
    category_filter = tracing_category_filter.TracingCategoryFilter(
        'x,-y,disabled-by-default-z,DELAY(7;foo)')
    config = tracing_config.TracingConfig()
    config.SetTracingCategoryFilter(category_filter)
    config.tracing_options.enable_systrace = True
    config.tracing_options.record_mode = tracing_options.RECORD_UNTIL_FULL
    config_string = config.GetChromeTraceConfigJsonString()
    self.assertEquals(
        '{'
          '"enable_systrace": true, '
          '"excluded_categories": ["y"], '
          '"included_categories": ["x", "disabled-by-default-z"], '
          '"record_mode": "record-until-full", '
          '"synthetic_delays": ["DELAY(7;foo)"]'
        '}',
        config_string)
