# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from dashboard import add_histograms
from tracing.value import histogram as histogram_module

class AddHistogramsTest(unittest.TestCase):
  def testInlineDenseSharedDiagnostics(self):
    histogram = histogram_module.Histogram('hist', 'count')
    histograms = histogram_module.HistogramSet([histogram])
    histograms.AddSharedDiagnostic('foo', histogram_module.Generic('bar'))
    add_histograms.InlineDenseSharedDiagnostics(histograms)
    self.assertTrue(histogram.diagnostics['foo'].is_inline)

  def testSparseDiagnosticsAreNotInlined(self):
    histogram = histogram_module.Histogram('hist', 'count')
    histograms = histogram_module.HistogramSet([histogram])
    histograms.AddSharedDiagnostic('foo', histogram_module.BuildbotInfo({
        'displayMasterName': 'dmn',
        'displayBotName': 'dbn',
        'buildbotMasterName': 'bbmn',
        'buildbotName': 'bbn',
        'buildNumber': 42,
        'logUri': 'uri',
    }))
    add_histograms.InlineDenseSharedDiagnostics(histograms)
    self.assertFalse(histogram.diagnostics['foo'].is_inline)
