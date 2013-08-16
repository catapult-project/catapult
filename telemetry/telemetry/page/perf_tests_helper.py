# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import

from telemetry.core import util

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'android')
from pylib import perf_tests_helper  # pylint: disable=F0401


GeomMeanAndStdDevFromHistogram = \
    perf_tests_helper.GeomMeanAndStdDevFromHistogram
PrintPerfResult = \
    perf_tests_helper.PrintPerfResult
PrintPages = \
    perf_tests_helper.PrintPages
