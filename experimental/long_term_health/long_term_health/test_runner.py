# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Helper function to run the benchmark.
"""
import datetime
import os
import subprocess

from long_term_health import utils


def RunBenchmark(path_to_apk):
  """Install the APK and run the benchmark on it.

  Args:
    path_to_apk(string): the *relative* path to the APK
  """
  apk_name = path_to_apk.split('/')[-1]
  subprocess.call(['adb', 'install', '-r', '-d', path_to_apk])
  subprocess.call(['../../../../tools/perf/run_benchmark',
                   '--browser=android-system-chrome',
                   '--pageset-repeat=1',  # could remove this later
                   '--results-label=%s' % apk_name,  # could remove this as well
                   # TODO(wangge):not sure if we should run in compatibility
                   # mode even for the later version, probably add a check in
                   # caller to determine if we should run it in compatibility
                   # mode and add an argument `run_in_compatibility_mode` to
                   # the `RunBenchmark` function
                   '--compatibility-mode',
                   '--story-filter=wikipedia',  # could remove this
                   # thinking of adding an argument to the tool to set this
                   '--output-dir=%s' % os.path.join(
                       utils.APP_ROOT, 'results', apk_name,
                       datetime.datetime.now().isoformat()),
                   # thinking of adding an argument to the tool to set this too
                   'system_health.memory_mobile'])
