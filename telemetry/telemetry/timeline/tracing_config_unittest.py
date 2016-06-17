# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from telemetry.timeline import tracing_category_filter
from telemetry.timeline import tracing_config


class TracingConfigTests(unittest.TestCase):
  def testDefault(self):
    config = tracing_config.TracingConfig()
    chrome_trace_config = config.chrome_trace_config

    # Trace config for startup tracing.
    self.assertEquals({
        'enable_systrace': False,
        'record_mode': 'record-as-much-as-possible'
    }, chrome_trace_config.GetChromeTraceConfigForStartupTracing())

    # Trace config for DevTools (modern API).
    self.assertEquals({
        'enableSystrace': False,
        'recordMode': 'recordAsMuchAsPossible'
    }, chrome_trace_config.GetChromeTraceConfigForDevTools())

    # Trace categories and options for DevTools (legacy API).
    self.assertFalse(
        chrome_trace_config.requires_modern_devtools_tracing_start_api)
    self.assertEquals(
        ('', 'record-as-much-as-possible'),
        chrome_trace_config.GetChromeTraceCategoriesAndOptionsForDevTools())

  def testBasic(self):
    category_filter = tracing_category_filter.TracingCategoryFilter(
        'x,-y,disabled-by-default-z,DELAY(7;foo)')
    config = tracing_config.TracingConfig()
    chrome_trace_config = config.chrome_trace_config
    chrome_trace_config.SetTracingCategoryFilter(category_filter)
    chrome_trace_config.enable_systrace = True
    chrome_trace_config.record_mode = tracing_config.RECORD_UNTIL_FULL

    # Trace config for startup tracing.
    self.assertEquals({
        'enable_systrace': True,
        'excluded_categories': ['y'],
        'included_categories': ['x', 'disabled-by-default-z'],
        'record_mode': 'record-until-full',
        'synthetic_delays': ['DELAY(7;foo)']
    }, chrome_trace_config.GetChromeTraceConfigForStartupTracing())

    # Trace config for DevTools (modern API).
    self.assertEquals({
        'enableSystrace': True,
        'excludedCategories': ['y'],
        'includedCategories': ['x', 'disabled-by-default-z'],
        'recordMode': 'recordUntilFull',
        'syntheticDelays': ['DELAY(7;foo)']
    }, chrome_trace_config.GetChromeTraceConfigForDevTools())

    # Trace categories and options for DevTools (legacy API).
    self.assertFalse(
        chrome_trace_config.requires_modern_devtools_tracing_start_api)
    self.assertEquals(
        ('x,disabled-by-default-z,-y,DELAY(7;foo)',
         'record-until-full,enable-systrace'),
        chrome_trace_config.GetChromeTraceCategoriesAndOptionsForDevTools())

  def testMemoryDumpConfigFormat(self):
    config = tracing_config.TracingConfig()
    config.chrome_trace_config.record_mode = tracing_config.ECHO_TO_CONSOLE
    dump_config = tracing_config.MemoryDumpConfig()
    config.chrome_trace_config.SetMemoryDumpConfig(dump_config)

    # Trace config for startup tracing.
    self.assertEquals({
        'enable_systrace': False,
        'memory_dump_config': {'triggers': []},
        'record_mode': 'trace-to-console'
    }, config.chrome_trace_config.GetChromeTraceConfigForStartupTracing())

    # Trace config for DevTools (modern API).
    self.assertEquals({
        'enableSystrace': False,
        'memoryDumpConfig': {'triggers': []},
        'recordMode': 'traceToConsole'
    }, config.chrome_trace_config.GetChromeTraceConfigForDevTools())

    # Trace categories and options for DevTools (legacy API).
    self.assertTrue(
        config.chrome_trace_config.requires_modern_devtools_tracing_start_api)
    with self.assertRaises(AssertionError):
      config.chrome_trace_config.GetChromeTraceCategoriesAndOptionsForDevTools()

    dump_config.AddTrigger('light', 250)
    dump_config.AddTrigger('detailed', 2000)

    # Trace config for startup tracing.
    self.assertEquals({
        'enable_systrace': False,
        'memory_dump_config': {
            'triggers': [
                {'mode': 'light', 'periodic_interval_ms': 250},
                {'mode': 'detailed', 'periodic_interval_ms': 2000}
            ]
        },
        'record_mode': 'trace-to-console'
    }, config.chrome_trace_config.GetChromeTraceConfigForStartupTracing())

    # Trace config for DevTools (modern API).
    self.assertEquals({
        'enableSystrace': False,
        'memoryDumpConfig': {
            'triggers': [
                {'mode': 'light', 'periodicIntervalMs': 250},
                {'mode': 'detailed', 'periodicIntervalMs': 2000}
            ]
        },
        'recordMode': 'traceToConsole'
    }, config.chrome_trace_config.GetChromeTraceConfigForDevTools())

    # Trace categories and options for DevTools (legacy API).
    self.assertTrue(
        config.chrome_trace_config.requires_modern_devtools_tracing_start_api)
    with self.assertRaises(AssertionError):
      config.chrome_trace_config.GetChromeTraceCategoriesAndOptionsForDevTools()
