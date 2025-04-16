# Copyright 2025 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# type-hint gets caught by pylint
def GetAndroidTarget(bot_name, err):
  """Return Android Target according to bot_name

  bot_name: string of bot_name (configuration)
  err: Exception, to throw when there's a missing definition

  Returns:
    string of the isolate target.
    defaults to performance_test_suite for non android targets.
  """
  # Each Android binary has its own target, and different bots use different
  # binaries. Mapping based off of Chromium's
  # //tools/perf/core/perf_data_generator.py
  if bot_name in ['android-go-perf', 'android-go-perf-pgo']:
    return 'performance_test_suite_android_clank_monochrome'
  if bot_name in ['android-go-wembley-perf']:
    return 'performance_test_suite_android_trichrome_chrome_google_bundle'
  if bot_name in [
      'android-pixel4-perf',
      'android-pixel4-perf-pgo',
      'android-pixel6-perf',
      'android-pixel6-perf-pgo',
      'android-pixel6-pro-perf',
      'android-pixel6-pro-perf-pgo',
      'android-pixel9-perf',
      'android-pixel9-pro-perf',
      'android-pixel9-pro-xl-perf',
      'android-pixel-fold-perf',
      'android-pixel-tangor-perf',
      'android-pixel-tangor-perf-cbb',
  ]:
    return 'performance_test_suite_android_trichrome_chrome_google_64_32_bundle'
  if 'android' in bot_name.lower():
    raise err

  return 'performance_test_suite'
