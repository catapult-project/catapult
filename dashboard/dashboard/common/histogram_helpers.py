# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Helper methods for working with histograms and diagnostics."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import re

from tracing.value.diagnostics import reserved_infos

_BENCHMARKS_WITH_SYNTHETIC_STATISTICS = [
    'ad_frames.fencedframe',
    'angle_perftests',
    'angle_trace_tests',
    'base_perftests',
    'blink_perf.accessibility',
    'blink_perf.display_locking',
    'blink_perf.sanitizer-api',
    'blink_perf.webaudio',
    'blink_perf.webcodecs',
    'blink_perf.webgl',
    'blink_perf.webgl_fast_call',
    'blink_perf.webgpu',
    'blink_perf.webgpu_fast_call',
    'chromecast_resource_sizes',
    'chromeperf.stats',
    'clamp',
    'components_perftests',
    'crosvm.binary_output',
    'dawn_perf_tests',
    'desktop_ui',
    'devtools.infra',
    'diffractor',
    'diffractor_test',
    'effects_performance_test',
    'example_cc_performance_test',
    'example_java_based_mobile_perf_test_android',
    'jetstream',
    'jetstream2-no-field-trials',
    'jetstream2-nominorms',
    'lacros_resource_sizes',
    'load_library_perf_tests',
    'loadline_phone_debug.crossbench',
    'media.desktop',
    'media.mobile',
    'media_backends_test',
    'memory.desktop',
    'octane-minorms',
    'octane-nominorms',
    'performance_browser_tests',
    'pinpoint.success',
    'platform.ReportDiskUsage',
    'power.desktop',
    'rendering.desktop',
    'rendering.desktop.notracing',
    'rendering.mobile',
    'rendering.mobile.notracing',
    'resource_sizes (CronetSample.apk)',
    'resource_sizes (Monochrome.minimal.apks)',
    'resource_sizes (SystemWebViewGoogle.minimal.apks)',
    'resource_sizes (TrichromeGoogle)',
    'sizes',
    'speedometer2-nominorms',
    'speedometer3-no-field-trials',
    'speedometer3-nominorms',
    'startup.mobile',
    'system_health.common_desktop',
    'system_health.common_mobile',
    'system_health.memory_desktop',
    'system_health.memory_mobile',
    'system_health.scroll_jank_mobile',
    'system_health.webview_startup',
    'tint_benchmark',
    'tracing_perftests',
    'v8',
    'v8.browsing_desktop',
    'v8.browsing_desktop-future',
    'v8.browsing_mobile',
    'v8.browsing_mobile-future',
    'v8.infra',
    'v8.runtime_stats.top_25',
    'v8.testing',
    'video_codec_perf_tests',
    'videocodec_test_rcc_videotoolbox',
    'views_perftests',
    'wasmpspdfkit',
    'webrtc',
    'webrtc_pc_regression_tests',
    'webrtc_perf_tests',
    'webrtc_perf_tests_mobile_internal',
    'webrtc_transparency_evaluation_test',
    'widevine-cdm.perf',
    'widevine-whitebox.perf',
    'xr.webxr.static',
]


def ShouldGenerateStatistics(benchmark_name):
  return benchmark_name in _BENCHMARKS_WITH_SYNTHETIC_STATISTICS or benchmark_name.startswith(
      'fuchsia.')

_STATS_BLACKLIST = ['std', 'count', 'max', 'min', 'sum']

SUITE_LEVEL_SPARSE_DIAGNOSTIC_NAMES = {
    reserved_infos.ARCHITECTURES.name,
    reserved_infos.BENCHMARKS.name,
    reserved_infos.BENCHMARK_DESCRIPTIONS.name,
    reserved_infos.BOTS.name,
    reserved_infos.BUG_COMPONENTS.name,
    reserved_infos.DOCUMENTATION_URLS.name,
    reserved_infos.GPUS.name,
    reserved_infos.MASTERS.name,
    reserved_infos.MEMORY_AMOUNTS.name,
    reserved_infos.OS_NAMES.name,
    reserved_infos.OS_VERSIONS.name,
    reserved_infos.OWNERS.name,
    reserved_infos.PRODUCT_VERSIONS.name,
}

HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_NAMES = {
    reserved_infos.ALERT_GROUPING.name,
    reserved_infos.DEVICE_IDS.name,
    reserved_infos.STORIES.name,
    reserved_infos.STORYSET_REPEATS.name,
    reserved_infos.STORY_TAGS.name,
}

SPARSE_DIAGNOSTIC_NAMES = SUITE_LEVEL_SPARSE_DIAGNOSTIC_NAMES.union(
    HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_NAMES)

ADD_HISTOGRAM_RELATED_DIAGNOSTICS = SPARSE_DIAGNOSTIC_NAMES.union({
    reserved_infos.BUILD_URLS.name,
    reserved_infos.CHROMIUM_COMMIT_POSITIONS.name,
    reserved_infos.LOG_URLS.name,
    reserved_infos.POINT_ID.name,
    reserved_infos.SUMMARY_KEYS.name,
    reserved_infos.TRACE_URLS.name,
})


def EscapeName(name):
  """Escapes a trace name so it can be stored in a row.

  Args:
    name: A string representing a name.

  Returns:
    An escaped version of the name.
  """
  return re.sub(r'[\:|=/#&,]', '_', name)


def ComputeTestPath(hist, ignore_grouping_label=False):
  # If a Histogram represents a summary across multiple stories, then its
  # 'stories' diagnostic will contain the names of all of the stories.
  # If a Histogram is not a summary, then its 'stories' diagnostic will contain
  # the singular name of its story.
  is_summary = list(hist.diagnostics.get(reserved_infos.SUMMARY_KEYS.name, []))

  grouping_label = GetGroupingLabelFromHistogram(
      hist) if not ignore_grouping_label else None

  is_ref = hist.diagnostics.get(reserved_infos.IS_REFERENCE_BUILD.name)
  if is_ref and len(is_ref) == 1:
    is_ref = is_ref.GetOnlyElement()

  story_name = hist.diagnostics.get(reserved_infos.STORIES.name)
  if story_name and len(story_name) == 1:
    story_name = story_name.GetOnlyElement()
  else:
    story_name = None

  return ComputeTestPathFromComponents(
      hist.name,
      grouping_label=grouping_label,
      story_name=story_name,
      is_summary=is_summary,
      is_ref=is_ref)


def ComputeTestPathFromComponents(hist_name,
                                  grouping_label=None,
                                  story_name=None,
                                  is_summary=None,
                                  is_ref=False,
                                  needs_escape=True):
  path = hist_name or ''

  if grouping_label and (not is_summary
                         or reserved_infos.STORY_TAGS.name in is_summary):
    path += '/' + grouping_label

  if story_name and not is_summary:
    if needs_escape:
      escaped_story_name = EscapeName(story_name)
      path += '/' + escaped_story_name
    else:
      path += '/' + story_name
    if is_ref:
      path += '_ref'
  elif is_ref:
    path += '/ref'

  return path


def GetGroupingLabelFromHistogram(hist):
  tags = hist.diagnostics.get(reserved_infos.STORY_TAGS.name) or []

  tags_to_use = [t.split(':') for t in tags if ':' in t]

  return '_'.join(v for _, v in sorted(tags_to_use))


def ShouldFilterStatistic(test_name, benchmark_name, stat_name):
  if test_name == 'benchmark_total_duration':
    return True
  if benchmark_name.startswith(
      'memory') and not benchmark_name.startswith('memory.long_running'):
    if 'memory:' in test_name and stat_name in _STATS_BLACKLIST:
      return True
  if benchmark_name.startswith('memory.long_running'):
    value_name = '%s_%s' % (test_name, stat_name)
    return not _ShouldAddMemoryLongRunningValue(value_name)
  if benchmark_name in ('media.desktop', 'media.mobile'):
    value_name = '%s_%s' % (test_name, stat_name)
    return not _ShouldAddMediaValue(value_name)
  if benchmark_name.startswith('system_health'):
    if stat_name in _STATS_BLACKLIST:
      return True
  return False


def _ShouldAddMediaValue(value_name):
  media_re = re.compile(
      r'(?<!dump)(?<!process)_(std|count|max|min|sum|pct_\d{4}(_\d+)?)$')
  return not media_re.search(value_name)


def _ShouldAddMemoryLongRunningValue(value_name):
  v8_re = re.compile(
      r'renderer_processes:'
      r'(reported_by_chrome:v8|reported_by_os:system_memory:[^:]+$)')
  if 'memory:chrome' in value_name:
    return ('renderer:subsystem:v8' in value_name
            or 'renderer:vmstats:overall' in value_name
            or bool(v8_re.search(value_name)))
  return 'v8' in value_name
