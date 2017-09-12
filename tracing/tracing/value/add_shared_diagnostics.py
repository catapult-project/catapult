# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json

from tracing.value import histogram
from tracing.value import histogram_set
from tracing.value.diagnostics import diagnostic


def AddSharedDiagnostics(
    histograms_json_filename, diagnostic_names_to_filenames):
  """Add shared Diagnostics to a set of histograms.

  Args:
    histograms_json_filename: path to a histograms JSON file.
    diagnostic_names_to_filenames: dict mapping names to filenames of
        serialized Diagnostics.

  Returns:
    The new histograms JSON with added shared diagnostic.
  """
  histogram_dicts = json.load(open(histograms_json_filename))
  histograms = histogram_set.HistogramSet()
  histograms.ImportDicts(histogram_dicts)

  for name, filename in diagnostic_names_to_filenames.iteritems():
    diag = diagnostic.Diagnostic.FromDict(json.load(open(filename)))
    histograms.AddSharedDiagnostic(name, diag)

  return json.dumps(histograms.AsDicts())


def AddValueDiagnostics(
    histograms_json_filename, diagnostic_names_to_values):
  """Adds shared GenericSets containing values to a set of histograms.

  Args:
    histograms_json_filename: path to a histograms JSON file.
    diagnostic_names_to_values: dict mapping names to JSONizable values.

  Returns:
    The new histograms JSON with added GenericSets.
  """
  histogram_dicts = json.load(open(histograms_json_filename))
  histograms = histogram_set.HistogramSet()
  histograms.ImportDicts(histogram_dicts)

  for name, value in diagnostic_names_to_values.iteritems():
    diag = histogram.GenericSet([value])
    histograms.AddSharedDiagnostic(name, diag)

  return json.dumps(histograms.AsDicts())
