# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import unittest
import tempfile

from tracing.value import histogram
from tracing.value import histogram_set
from tracing.value.diagnostics import add_reserved_diagnostics
from tracing.value.diagnostics import generic_set

class AddReservedDiagnosticsUnittest(unittest.TestCase):

  def testAddReservedDiagnostics_Adds(self):
    h = histogram.Histogram('foo', 'count')
    hs = histogram_set.HistogramSet([h])

    f = tempfile.NamedTemporaryFile(delete=False)
    json.dump(hs.AsDicts(), f)
    f.close()
    new_hs_json = add_reserved_diagnostics.AddReservedDiagnostics(
        f.name, {'benchmarks': 'bar'})

    new_hs = histogram_set.HistogramSet()
    new_hs.ImportDicts(json.loads(new_hs_json))
    os.remove(f.name)

    self.assertEqual(len(new_hs), 2)
    new_h = [h for h in new_hs.GetHistogramsNamed('foo') if 'isSummary' in
             h.diagnostics][0]

    self.assertEqual(len(new_h.diagnostics), 2)
    self.assertIsInstance(new_h.diagnostics['benchmarks'],
                          generic_set.GenericSet)
    self.assertEqual(len(new_h.diagnostics['benchmarks']), 1)
    self.assertEqual(new_h.diagnostics['benchmarks'].GetOnlyElement(), 'bar')
