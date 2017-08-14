# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import tempfile
import unittest

from tracing.value import add_shared_diagnostic
from tracing.value import histogram
from tracing.value import histogram_set


class AddSharedDiagnosticTest(unittest.TestCase):
  def testAddSharedDiagnostic(self):
    hf = tempfile.NamedTemporaryFile(delete=False)
    h = histogram.Histogram('foo', 'count')
    hs = histogram_set.HistogramSet([h])
    json.dump(hs.AsDicts(), hf)
    hf.close()

    df = tempfile.NamedTemporaryFile(delete=False)
    d = histogram.GenericSet(['bar'])
    json.dump(d.AsDict(), df)
    df.close()

    new_hs_data = add_shared_diagnostic.AddSharedDiagnostic(
        hf.name, 'foo', df.name).stdout
    new_hs = histogram_set.HistogramSet()
    new_hs.ImportDicts(json.loads(new_hs_data))
    new_hs.ResolveRelatedHistograms()
    new_h = new_hs.GetFirstHistogram()

    self.assertEqual(new_h.diagnostics['foo'], d)
