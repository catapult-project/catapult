# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import functools

from dashboard.common import report_query
from dashboard.models import report_template
from dashboard import update_test_suite_descriptors


MEMORY_PHASES = [
    ('Foreground', ['load:', 'browse:']),
    ('Background', ['background:'])
]

MEMORY_METRICS = [
    ('Java Heap', 'system_memory:java_heap'),
    ('Native Heap', 'system_memory:native_heap'),
    ('Android Graphics', 'gpu_memory'),
    ('Overall PSS', 'system_memory')
]

STARTUP_BY_BROWSER = {
    'chrome': {
        'testSuites': ['start_with_url.cold.startup_pages'],
        'measurement': 'foreground_tab_request_start',
        'testCases': ['http://bbc.co.uk']
    },
    'webview': {
        'testSuites': ['system_health.webview_startup'],
        'measurement': 'webview_startup_wall_time_avg',
        'testCases': ['load:chrome:blank']
    }
}


def MemoizeWithTimeout(**kwargs):
  """Memoize the value returned by a function that takes no arguments."""
  duration = datetime.timedelta(**kwargs)
  def Decorator(f):
    f._value = None
    f._expires_at = None
    @functools.wraps(f)
    def Replacement():
      if f._expires_at is None or datetime.datetime.utcnow() > f._expires_at:
        f._value = f()
        f._expires_at = datetime.datetime.utcnow() + duration
      return f._value
    return Replacement
  return Decorator


@MemoizeWithTimeout(hours=12)
def GetSystemHealthDescriptors():
  return update_test_suite_descriptors.FetchCachedTestSuiteDescriptor(
      'system_health.memory_mobile')


def IterPhasesAndTestCases():
  descriptors = GetSystemHealthDescriptors()

  for phase, prefixes in MEMORY_PHASES:
    # Select test cases that start with any of the given prefixes.
    test_cases = [
        test_case for test_case in descriptors['cases']
        if any(test_case.startswith(prefix) for prefix in prefixes)]
    yield phase, test_cases


def IterTemplateRows(browser, bot):
  for phase, test_cases in IterPhasesAndTestCases():
    for label, component in MEMORY_METRICS:
      yield {
          'label': ':'.join([phase, label]),
          'testSuites': ['system_health.memory_mobile'],
          'bots': [bot],
          'measurement': ':'.join([
              'memory', browser, 'all_processes:reported_by_os', component,
              'proportional_resident_size']),
          'testCases': test_cases
      }
  yield {
      'label': 'Battery:Energy Consumption',
      'testSuites': ['power.typical_10_mobile'],
      'bots': [bot],
      'measurement': 'application_energy_consumption_mwh',
      'testCases': []
  }
  yield dict(STARTUP_BY_BROWSER[browser], label='Startup:Time', bots=[bot])


def CreateSystemHealthReport(template_id, name, builder, is_internal, modified):
  # The browser (Chrome/WebView) is always the second part of the report name,
  # and is used to build the right template.
  browser = name.split(':')[1].lower()
  master = 'ClankInternal' if is_internal else 'ChromiumPerf'
  bot = ':'.join([master, builder])

  @report_template.Static(
      template_id=template_id,
      name=name,
      internal_only=is_internal,
      modified=modified)
  def Report(revisions):
    # Template is updated on each call to the handler to make sure that we use
    # an up to date set of foreground/background stories.
    template = {
        'rows': list(IterTemplateRows(browser, bot)),
        'statistics': ['avg', 'std', 'max'],
        'url': 'https://bit.ly/system-health-benchmarks'
    }
    return report_query.ReportQuery(template, revisions)

  return Report


CreateSystemHealthReport(
    template_id=2013652838,
    name='Health:Chrome:Android Go (Internal)',
    builder='perf-go-phone-1024',
    is_internal=True,
    modified=datetime.datetime(2018, 8, 2))

CreateSystemHealthReport(
    template_id=434658613,
    name='Health:Chrome:Nexus 5 (Internal)',
    builder='health-plan-clankium-phone',
    is_internal=True,
    modified=datetime.datetime(2018, 8, 2))

CreateSystemHealthReport(
    template_id=1371943537,
    name='Health:WebView:Android Go (Internal)',
    builder='perf-go-webview-phone',
    is_internal=True,
    modified=datetime.datetime(2018, 8, 2))

CreateSystemHealthReport(
    template_id=191176182,
    name='Health:WebView:Nexus 5 (Internal)',
    builder='health-plan-webview-phone',
    is_internal=True,
    modified=datetime.datetime(2018, 8, 2))
