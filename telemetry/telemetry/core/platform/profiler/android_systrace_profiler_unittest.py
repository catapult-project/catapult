# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import os
import shutil
import tempfile
import zipfile

from telemetry import benchmark
from telemetry.core.platform.profiler import android_systrace_profiler
from telemetry.unittest import tab_test_case


class TestAndroidSystraceProfiler(tab_test_case.TabTestCase):
  @benchmark.Enabled('android')
  def testSystraceProfiler(self):
    try:
      out_dir = tempfile.mkdtemp()
      # pylint: disable=W0212
      profiler = android_systrace_profiler.AndroidSystraceProfiler(
          self._browser._browser_backend,
          self._browser._platform_backend,
          os.path.join(out_dir, 'systrace'),
          {})
      result = profiler.CollectProfile()[0]
      assert zipfile.is_zipfile(result)
      with zipfile.ZipFile(result) as z:
        self.assertEquals(len(z.namelist()), 2)
    finally:
      shutil.rmtree(out_dir)
