# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import absolute_import

from telemetry.core import util

util.AddDirToPythonPath(util.GetChromiumSrcDir(), 'build', 'util', 'lib',
                        'common')
import perf_tests_results_helper  # pylint: disable=F0401


FlattenList = \
    perf_tests_results_helper.FlattenList
GeomMeanAndStdDevFromHistogram = \
    perf_tests_results_helper.GeomMeanAndStdDevFromHistogram
PrintPerfResult = \
    perf_tests_results_helper.PrintPerfResult
PrintPages = \
    perf_tests_results_helper.PrintPages
