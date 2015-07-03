# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import unittest


_TRACING_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir))


def IsTestExpectedToFail(test_file_name):
  """ Return whether html or js file that yet runnable by d8_runner.

      This offers a solution to incremental enable more html files that are
      runnable by d8. If you add a new html/js files that are not compatible
      with d8_runner, please contact dsinclair@ or nduca@ for how to proceed.
  """
  return os.path.abspath(test_file_name) in GetD8NonCompatibleFiles()


def GetD8NonCompatibleFiles():
  """ Returns the list of files that are expected to throw exeception when run
  by d8_runner.
  """
  if not _D8_BLACK_LIST_FILES:
    for f in _REL_PATH_D8_BLACK_LIST_FILES:
      _D8_BLACK_LIST_FILES.add(os.path.join(_TRACING_DIR, f))
  return _D8_BLACK_LIST_FILES


_D8_BLACK_LIST_FILES = set()


# TODO(dsinclair, nduca, nednguyen): burn down this set.
# (https://github.com/google/trace-viewer/issues/984)
_REL_PATH_D8_BLACK_LIST_FILES = {
  "tracing/base/base64_test.html",
  "tracing/base/bbox2_test.html",
  "tracing/base/color_test.html",
  "tracing/base/deep_utils_test.html",
  "tracing/base/event_target_test.html",
  "tracing/base/extension_registry_test.html",
  "tracing/base/interval_tree_test.html",
  "tracing/base/iteration_helpers_test.html",
  "tracing/base/math_test.html",
  "tracing/base/properties_test.html",
  "tracing/base/quad_test.html",
  "tracing/base/raf_test.html",
  "tracing/base/range_test.html",
  "tracing/base/range_utils_test.html",
  "tracing/base/rect_test.html",
  "tracing/base/settings_test.html",
  "tracing/base/sorted_array_utils_test.html",
  "tracing/base/statistics_test.html",
  "tracing/base/task_test.html",
  "tracing/base/tests.html",
  "tracing/base/units/size_in_bytes_test.html",
  "tracing/base/units/time_duration_test.html",
  "tracing/base/units/time_stamp_test.html",
  "tracing/base/units/time_test.html",
  "tracing/base/unittest/html_test_results.html",
  "tracing/base/unittest/interactive_test_runner.html",
  "tracing/base/unittest/test_case_test.html",
  "tracing/base/unittest_test.html",
  "tracing/base/utils_test.html",
  "tracing/core/filter_test.html",
  "tracing/core/scripting_controller_test.html",
  "tracing/core/selection_controller_test.html",
  "tracing/core/selection_test.html",
  "tracing/extras/android/android_auditor_test.html",
  "tracing/extras/android/android_model_helper_test.html",
  "tracing/extras/chrome/cc/display_item_list_test.html",
  "tracing/extras/chrome/cc/input_latency_async_slice_test.html",
  "tracing/extras/chrome/cc/layer_tree_host_impl_test.html",
  "tracing/extras/chrome/cc/picture_test.html",
  "tracing/extras/chrome/cc/tile_test.html",
  "tracing/extras/chrome/cc/util_test.html",
  "tracing/extras/chrome/chrome_auditor_test.html",
  "tracing/extras/chrome/chrome_browser_helper_test.html",
  "tracing/extras/chrome/chrome_model_helper_test.html",
  "tracing/extras/chrome_config.html",
  "tracing/extras/chrome/gpu/gpu_async_slice_test.html",
  "tracing/extras/chrome/gpu/state_test.html",
  "tracing/extras/chrome/layout_object_test.html",
  "tracing/extras/full_config.html",
  "tracing/extras/importer/battor_importer_test.html",
  "tracing/extras/importer/ddms_importer_test.html",
  "tracing/extras/importer/etw/etw_importer_test.html",
  "tracing/extras/importer/etw/eventtrace_parser_test.html",
  "tracing/extras/importer/etw/process_parser_test.html",
  "tracing/extras/importer/etw/thread_parser_test.html",
  "tracing/extras/importer/gzip_importer_test.html",
  "tracing/extras/importer/linux_perf/android_parser_test.html",
  "tracing/extras/importer/linux_perf/bus_parser_test.html",
  "tracing/extras/importer/linux_perf/clock_parser_test.html",
  "tracing/extras/importer/linux_perf/cpufreq_parser_test.html",
  "tracing/extras/importer/linux_perf/disk_parser_test.html",
  "tracing/extras/importer/linux_perf/drm_parser_test.html",
  "tracing/extras/importer/linux_perf/exynos_parser_test.html",
  "tracing/extras/importer/linux_perf/ftrace_importer_test.html",
  "tracing/extras/importer/linux_perf/gesture_parser_test.html",
  "tracing/extras/importer/linux_perf/i915_parser_test.html",
  "tracing/extras/importer/linux_perf/irq_parser_test.html",
  "tracing/extras/importer/linux_perf/kfunc_parser_test.html",
  "tracing/extras/importer/linux_perf/mali_parser_test.html",
  "tracing/extras/importer/linux_perf/memreclaim_parser_test.html",
  "tracing/extras/importer/linux_perf/power_parser_test.html",
  "tracing/extras/importer/linux_perf/regulator_parser_test.html",
  "tracing/extras/importer/linux_perf/sched_parser_test.html",
  "tracing/extras/importer/linux_perf/sync_parser_test.html",
  "tracing/extras/importer/linux_perf/workqueue_parser_test.html",
  "tracing/extras/importer/trace2html_importer_test.html",
  "tracing/extras/importer/trace_event_importer_perf_test.html",
  "tracing/extras/importer/trace_event_importer_test.html",
  "tracing/extras/importer/v8/v8_log_importer_test.html",
  "tracing/extras/lean_config.html",
  "tracing/extras/net/net_async_slice_test.html",
  "tracing/extras/rail/rail_interaction_record_test.html",
  "tracing/extras/rail/rail_ir_finder_test.html",
  "tracing/extras/rail/rail_score_test.html",
  "tracing/extras/rail/response_interaction_record_test.html",
  "tracing/extras/systrace_config.html",
  "tracing/extras/tcmalloc/heap_test.html",
  "tracing/extras/tquery/tquery_test.html",
  "tracing/model/annotation_test.html",
  "tracing/model/async_slice_group.html",
  "tracing/model/async_slice_group_test.html",
  "tracing/model/attribute_test.html",
  "tracing/model/container_memory_dump_test.html",
  "tracing/model/counter_sample_test.html",
  "tracing/model/counter_test.html",
  "tracing/model/cpu_test.html",
  "tracing/model/event_test.html",
  "tracing/model/global_memory_dump_test.html",
  "tracing/model/kernel_test.html",
  "tracing/model/memory_allocator_dump_test.html",
  "tracing/model/model_indices_test.html",
  "tracing/model/model_settings_test.html",
  "tracing/model/model_test.html",
  "tracing/model/multi_async_slice_sub_view_test.html",
  "tracing/model/object_collection_test.html",
  "tracing/model/object_instance_test.html",
  "tracing/model/object_snapshot_test.html",
  "tracing/model/process_memory_dump_test.html",
  "tracing/model/process_test.html",
  "tracing/model/proxy_selectable_item_test.html",
  "tracing/model/sample_test.html",
  "tracing/model/selectable_item_test.html",
  "tracing/model/single_async_slice_sub_view_test.html",
  "tracing/model/slice_group_test.html",
  "tracing/model/slice_test.html",
  "tracing/model/thread_test.html",
  "tracing/model/timed_event_test.html",
  "tracing/model/time_to_object_instance_map_test.html",
  "tracing/trace2html.html",
  "tracing/trace_viewer.html",
}
