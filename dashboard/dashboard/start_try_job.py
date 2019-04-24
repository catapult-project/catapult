# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint containing server-side functionality for bisect try jobs."""

import re

from dashboard import list_tests
from dashboard.common import utils


_NON_TELEMETRY_TEST_COMMANDS = {
    'angle_perftests': [
        './out/Release/angle_perftests',
        '--test-launcher-print-test-stdio=always',
        '--test-launcher-jobs=1',
    ],
    'cc_perftests': [
        './out/Release/cc_perftests',
        '--test-launcher-print-test-stdio=always',
        '--verbose',
    ],
    'idb_perf': [
        './out/Release/performance_ui_tests',
        '--gtest_filter=IndexedDBTest.Perf',
    ],
    'load_library_perf_tests': [
        './out/Release/load_library_perf_tests',
        '--single-process-tests',
    ],
    'media_perftests': [
        './out/Release/media_perftests',
        '--single-process-tests',
    ],
    'performance_browser_tests': [
        './out/Release/performance_browser_tests',
        '--test-launcher-print-test-stdio=always',
        '--enable-gpu',
    ],
    'resource_sizes': [
        'src/build/android/resource_sizes.py',
        '--chromium-output-directory {CHROMIUM_OUTPUT_DIR}',
        '--chartjson',
        '{CHROMIUM_OUTPUT_DIR}',
    ],
    'tracing_perftests': [
        './out/Release/tracing_perftests',
        '--test-launcher-print-test-stdio=always',
        '--verbose',
    ],
    'v8': [],  # V8 does not support recipe bisects.
}
_NON_TELEMETRY_ANDROID_COMMAND = 'src/build/android/test_runner.py '\
                                 'gtest --release -s %(suite)s --verbose'
_NON_TELEMETRY_ANDROID_SUPPORTED_TESTS = ['cc_perftests', 'tracing_perftests']

_DISABLE_STORY_FILTER_SUITE_LIST = set([
    'octane',  # Has a single story.
])


def _IsNonTelemetrySuiteName(suite):
  return (suite in _NON_TELEMETRY_TEST_COMMANDS or
          suite.startswith('resource_sizes'))


def GuessStoryFilter(test_path):
  """Returns a suitable "story filter" to use in the bisect config.

  Args:
    test_path: The slash-separated test path used by the dashboard.

  Returns:
    A regex pattern that matches the story referred to by the test_path, or
    an empty string if the test_path does not refer to a story and no story
    filter should be used.
  """
  test_path_parts = test_path.split('/')
  suite_name, story_name = test_path_parts[2], test_path_parts[-1]
  if any([
      _IsNonTelemetrySuiteName(suite_name),
      suite_name in _DISABLE_STORY_FILTER_SUITE_LIST,
      suite_name.startswith('media.') and '.html?' not in story_name,
      suite_name.startswith('webrtc.')]):
    return ''
  test_key = utils.TestKey(test_path)
  subtest_keys = list_tests.GetTestDescendants(test_key)
  try:
    subtest_keys.remove(test_key)
  except ValueError:
    pass
  if subtest_keys:  # Stories do not have subtests.
    return ''

  # memory.top_10_mobile runs pairs of "{url}" and "after_{url}" stories to
  # gather foreground and background measurements. Story filters may be used,
  # but we need to strip off the "after_" prefix so that both stories in the
  # pair are always run together.
  # TODO(crbug.com/761014): Remove when benchmark is deprecated.
  if suite_name == 'memory.top_10_mobile' and story_name.startswith('after_'):
    story_name = story_name[len('after_'):]

  # During import, some chars in story names got replaced by "_" so they
  # could be safely included in the test_path. At this point we don't know
  # what the original characters were. Additionally, some special characters
  # and argument quoting are not interpreted correctly, e.g. by bisect
  # scripts (crbug.com/662472). We thus keep only a small set of "safe chars"
  # and replace all others with match-any-character regex dots.
  return re.sub(r'[^a-zA-Z0-9]', '.', story_name)
