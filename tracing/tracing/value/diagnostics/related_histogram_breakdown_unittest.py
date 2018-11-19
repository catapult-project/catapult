# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from tracing.value import histogram
from tracing.value import histogram_unittest
from tracing.value.diagnostics import diagnostic
from tracing.value.diagnostics import related_histogram_breakdown


class RelatedHistogramBreakdownUnittest(unittest.TestCase):
  def testRoundtrip(self):
    breakdown = related_histogram_breakdown.RelatedHistogramBreakdown()
    hista = histogram.Histogram('a', 'unitless')
    histb = histogram.Histogram('b', 'unitless')
    breakdown.Add(hista)
    breakdown.Add(histb)
    d = breakdown.AsDict()
    clone = diagnostic.Diagnostic.FromDict(d)
    self.assertEqual(
        histogram_unittest.ToJSON(d), histogram_unittest.ToJSON(clone.AsDict()))
    self.assertEqual(hista.guid, clone.Get('a').guid)
    self.assertEqual(histb.guid, clone.Get('b').guid)
