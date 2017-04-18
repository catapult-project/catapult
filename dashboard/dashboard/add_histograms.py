# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""URL endpoint for adding new histograms to the dashboard."""

from tracing.value import histogram as histogram_module

SUITE_LEVEL_SPARSE_DIAGNOSTIC_TYPES = set(
    [histogram_module.BuildbotInfo, histogram_module.DeviceInfo])
HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_TYPES = set(
    [histogram_module.TelemetryInfo])
SPARSE_DIAGNOSTIC_TYPES = SUITE_LEVEL_SPARSE_DIAGNOSTIC_TYPES.union(
    HISTOGRAM_LEVEL_SPARSE_DIAGNOSTIC_TYPES)

def InlineDenseSharedDiagnostics(histograms):
  for histogram in histograms:
    diagnostics = histogram.diagnostics
    for diagnostic in diagnostics.itervalues():
      if type(diagnostic) not in SPARSE_DIAGNOSTIC_TYPES:
        diagnostic.Inline()
