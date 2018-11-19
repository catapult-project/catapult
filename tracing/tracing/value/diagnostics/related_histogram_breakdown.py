# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tracing.value import histogram


class RelatedHistogramBreakdown(histogram.RelatedHistogramMap):
  __slots__ = '_color_scheme',

  def __init__(self):
    super(RelatedHistogramBreakdown, self).__init__()
    self._color_scheme = None

  def Set(self, name, hist):
    if not isinstance(hist, histogram.HistogramRef):
      assert isinstance(hist, histogram.Histogram), (
          'Expected Histogram, found %s: "%r"' % (type(hist).__name__, hist))
      # All Histograms must have the same unit.
      for _, other_hist in self:
        expected_unit = other_hist.unit
        assert expected_unit == hist.unit, (
            'Units mismatch ' + expected_unit + ' != ' + hist.unit)
        break  # Only the first Histogram needs to be checked.
    super(RelatedHistogramBreakdown, self).Set(name, hist)

  def _AsDictInto(self, d):
    histogram.RelatedHistogramMap._AsDictInto(self, d)
    if self._color_scheme:
      d['colorScheme'] = self._color_scheme

  @staticmethod
  def FromDict(d):
    result = RelatedHistogramBreakdown()
    for name, guid in d['values'].items():
      result.Set(name, histogram.HistogramRef(guid))
    if 'colorScheme' in d:
      result._color_scheme = d['colorScheme']
    return result

