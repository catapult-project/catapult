# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_config


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
    config.enable_systrace = True
    config.record_mode = tracing_config.RECORD_UNTIL_FULL
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

  def testMemoryDumpConfigFormat(self):
    config = tracing_config.TracingConfig()
    dump_config = tracing_config.MemoryDumpConfig()
    config.SetMemoryDumpConfig(dump_config)
    self.assertEquals(
        '{'
          '"memory_dump_config": {"triggers": []}, '
          '"record_mode": "record-as-much-as-possible"'
        '}',
        config.GetChromeTraceConfigJsonString())

    dump_config.AddTrigger("light", 250)
    dump_config.AddTrigger("detailed", 2000)
    config.SetMemoryDumpConfig(dump_config)
    self.assertEquals(
        '{'
          '"memory_dump_config": '
            '{'
              '"triggers": ['
                '{"mode": "light", "periodic_interval_ms": 250}, '
                '{"mode": "detailed", "periodic_interval_ms": 2000}'
              ']'
            '}, '
          '"record_mode": "record-as-much-as-possible"'
        '}',
        config.GetChromeTraceConfigJsonString())
