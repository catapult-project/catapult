# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from tracing.value import histogram_set
from tracing.value import merge_histograms
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import reserved_infos


ALL_NAMES = list(reserved_infos.AllNames())


def AddReservedDiagnostics(histogram_set_path, names_to_values):
  # TODO(#3987): Refactor recipes to call merge_histograms separately.
  dicts_across_repeats = merge_histograms.MergeHistograms(histogram_set_path, (
      'name', 'stories'))
  dicts_across_stories = merge_histograms.MergeHistograms(histogram_set_path, (
      'name',))

  histograms = histogram_set.HistogramSet()
  histograms.ImportDicts(dicts_across_stories)
  histograms.ResolveRelatedHistograms()
  for histogram in histograms:
    histogram.diagnostics[
        reserved_infos.IS_SUMMARY.name] = generic_set.GenericSet([True])

  histograms.ImportDicts(dicts_across_repeats)
  histograms.DeduplicateDiagnostics()

  for name, value in names_to_values.iteritems():
    assert name in ALL_NAMES
    histograms.AddSharedDiagnostic(name, generic_set.GenericSet([value]))

  return json.dumps(histograms.AsDicts())
