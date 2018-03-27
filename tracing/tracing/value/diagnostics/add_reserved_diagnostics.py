# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import json
import os
import tempfile

from tracing.value import histogram_set
from tracing.value import merge_histograms
from tracing.value.diagnostics import generic_set
from tracing.value.diagnostics import reserved_infos


ALL_NAMES = list(reserved_infos.AllNames())


def _LoadHistogramSet(dicts):
  hs = histogram_set.HistogramSet()
  hs.ImportDicts(dicts)
  hs.ResolveRelatedHistograms()
  return hs


@contextlib.contextmanager
def TempFile():
  try:
    temp = tempfile.NamedTemporaryFile(delete=False)
    yield temp
  finally:
    os.unlink(temp.name)


def AddReservedDiagnostics(histogram_dicts, names_to_values):
  # We need to generate summary statistics for anything that had a story, so
  # filter out every histogram with no stories, then merge. If you keep the
  # histograms with no story, you end up with duplicates.
  hs_with_stories = _LoadHistogramSet(histogram_dicts)
  hs_with_stories.FilterHistograms(
      lambda h: not h.diagnostics.get(reserved_infos.STORIES.name, []))

  hs_with_no_stories = _LoadHistogramSet(histogram_dicts)
  hs_with_no_stories.FilterHistograms(
      lambda h: h.diagnostics.get(reserved_infos.STORIES.name, []))

  # TODO(#3987): Refactor recipes to call merge_histograms separately.
  with TempFile() as temp:
    temp.write(json.dumps(hs_with_stories.AsDicts()))
    temp.close()

    # This call combines all repetitions of a metric for a given story into a
    # single histogram.
    dicts_across_repeats = merge_histograms.MergeHistograms(temp.name, (
        'name', 'stories'))
    # This call creates summary metrics across each set of stories.
    dicts_across_stories = merge_histograms.MergeHistograms(temp.name, (
        'name',))

  # Now load everything into one histogram set. First we load the summary
  # histograms, since we need to mark them with IS_SUMMARY.
  # After that we load the rest, and then apply all the diagnostics specified
  # on the command line. Finally, since we end up with a lot of diagnostics
  # that no histograms refer to, we make sure to prune those.
  histograms = histogram_set.HistogramSet()
  histograms.ImportDicts(dicts_across_stories)
  for h in histograms:
    h.diagnostics[
        reserved_infos.IS_SUMMARY.name] = generic_set.GenericSet([True])

  histograms.ImportDicts(dicts_across_repeats)
  histograms.ImportDicts(hs_with_no_stories.AsDicts())
  histograms.DeduplicateDiagnostics()
  for name, value in names_to_values.iteritems():
    assert name in ALL_NAMES
    histograms.AddSharedDiagnostic(name, generic_set.GenericSet([value]))
  histograms.RemoveOrphanedDiagnostics()

  return json.dumps(histograms.AsDicts())
