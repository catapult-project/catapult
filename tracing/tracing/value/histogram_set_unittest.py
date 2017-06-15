# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from tracing.value import histogram
from tracing.value import histogram_set


class HistogramSetUnittest(unittest.TestCase):

  def testRelatedHistogramSet(self):
    a = histogram.Histogram('a', 'unitless')
    b = histogram.Histogram('b', 'unitless')
    c = histogram.Histogram('c', 'unitless')
    a.diagnostics['rhs'] = histogram.RelatedHistogramSet([b, c])

    # Don't serialize c yet.
    hists = histogram_set.HistogramSet([a, b])
    hists2 = histogram_set.HistogramSet()
    hists2.ImportDicts(hists.AsDicts())
    hists2.ResolveRelatedHistograms()
    a2 = hists2.GetHistogramsNamed('a')
    self.assertEqual(len(a2), 1)
    a2 = a2[0]
    self.assertEqual(a2.guid, a.guid)
    self.assertIsInstance(a2, histogram.Histogram)
    self.assertIsNot(a2, a)
    b2 = hists2.GetHistogramsNamed('b')
    self.assertEqual(len(b2), 1)
    b2 = b2[0]
    self.assertEqual(b2.guid, b.guid)
    self.assertIsInstance(b2, histogram.Histogram)
    self.assertIsNot(b2, b)
    rhs2 = a2.diagnostics['rhs']
    self.assertIsInstance(rhs2, histogram.RelatedHistogramSet)
    self.assertEqual(len(rhs2), 2)

    # Assert that b and c are in a2's RelatedHistogramSet, rhs2.
    rhs2hs = list(rhs2)
    rhs2guids = [h.guid for h in rhs2hs]
    b2i = rhs2guids.index(b.guid)
    self.assertIs(rhs2hs[b2i], b2)

    c2i = rhs2guids.index(c.guid)
    self.assertIsInstance(rhs2hs[c2i], histogram.HistogramRef)

    # Now serialize c and add it to hists2.
    hists2.ImportDicts([c.AsDict()])
    hists2.ResolveRelatedHistograms()

    c2 = hists2.GetHistogramsNamed('c')
    self.assertEqual(len(c2), 1)
    c2 = c2[0]
    self.assertEqual(c2.guid, c.guid)
    self.assertIsNot(c2, c)

    rhs2hs = list(rhs2)
    rhs2guids = [h.guid for h in rhs2hs]
    b2i = rhs2guids.index(b.guid)
    c2i = rhs2guids.index(c.guid)
    self.assertIs(b2, rhs2hs[b2i])
    self.assertIs(c2, rhs2hs[c2i])

  def testRelatedHistogramMap(self):
    a = histogram.Histogram('a', 'unitless')
    b = histogram.Histogram('b', 'unitless')
    c = histogram.Histogram('c', 'unitless')
    rhm = histogram.RelatedHistogramMap()
    rhm.Set('y', b)
    rhm.Set('z', c)
    a.diagnostics['rhm'] = rhm

    # Don't serialize c yet.
    hists = histogram_set.HistogramSet([a, b])
    hists2 = histogram_set.HistogramSet()
    hists2.ImportDicts(hists.AsDicts())
    hists2.ResolveRelatedHistograms()
    a2 = hists2.GetHistogramsNamed('a')
    self.assertEqual(len(a2), 1)
    a2 = a2[0]
    self.assertEqual(a2.guid, a.guid)
    self.assertIsInstance(a2, histogram.Histogram)
    self.assertIsNot(a2, a)
    b2 = hists2.GetHistogramsNamed('b')
    self.assertEqual(len(b2), 1)
    b2 = b2[0]
    self.assertEqual(b2.guid, b.guid)
    self.assertIsInstance(b2, histogram.Histogram)
    self.assertIsNot(b2, b)
    rhm2 = a2.diagnostics['rhm']
    self.assertIsInstance(rhm2, histogram.RelatedHistogramMap)
    self.assertEqual(len(rhm2), 2)

    # Assert that b and c are in a2's RelatedHistogramMap, rhm2.
    self.assertIs(b2, rhm2.Get('y'))
    self.assertIsInstance(rhm2.Get('z'), histogram.HistogramRef)

    # Now serialize c and add it to hists2.
    hists2.ImportDicts([c.AsDict()])
    hists2.ResolveRelatedHistograms()

    c2 = hists2.GetHistogramsNamed('c')
    self.assertEqual(len(c2), 1)
    c2 = c2[0]
    self.assertEqual(c2.guid, c.guid)
    self.assertIsNot(c2, c)

    self.assertIs(b2, rhm2.Get('y'))
    self.assertIs(c2, rhm2.Get('z'))

  def testGetSharedDiagnosticsOfType(self):
    d0 = histogram.Generic('foo')
    d1 = histogram.TelemetryInfo()
    hs = histogram_set.HistogramSet()
    hs.AddSharedDiagnostic('generic', d0)
    hs.AddSharedDiagnostic('generic', d1)
    diagnostics = hs.GetSharedDiagnosticsOfType(histogram.Generic)
    self.assertEqual(len(diagnostics), 1)
    self.assertIsInstance(diagnostics[0], histogram.Generic)

  def testImportDicts(self):
    hist = histogram.Histogram('', 'unitless')
    hists = histogram_set.HistogramSet([hist])
    hists2 = histogram_set.HistogramSet()
    hists2.ImportDicts(hists.AsDicts())
    self.assertEqual(len(hists), len(hists2))

  def testAddHistogramRaises(self):
    hist = histogram.Histogram('', 'unitless')
    hists = histogram_set.HistogramSet([hist])
    with self.assertRaises(Exception):
      hists.AddHistogram(hist)
    hist2 = histogram.Histogram('', 'unitless')
    # Do not ever do this in real code:
    hist2.guid = hist.guid
    with self.assertRaises(Exception):
      hists.AddHistogram(hist2)

  def testSharedDiagnostic(self):
    hist = histogram.Histogram('', 'unitless')
    hists = histogram_set.HistogramSet([hist])
    diag = histogram.Generic('shared')
    hists.AddSharedDiagnostic('generic', diag)

    # Serializing a single Histogram with a single shared diagnostic should
    # produce 2 dicts.
    ds = hists.AsDicts()
    self.assertEqual(len(ds), 2)
    self.assertEqual(diag.AsDict(), ds[0])

    # The serialized Histogram should refer to the shared diagnostic by its
    # guid.
    self.assertEqual(ds[1]['diagnostics']['generic'], diag.guid)

    # Deserialize ds.
    hists2 = histogram_set.HistogramSet()
    hists2.ImportDicts(ds)
    self.assertEqual(len(hists2), 1)
    hist2 = [h for h in hists2][0]

    # The diagnostic reference should be deserialized as a DiagnosticRef until
    # resolveRelatedHistograms is called.
    self.assertIsInstance(
        hist2.diagnostics.get('generic'), histogram.DiagnosticRef)
    hists2.ResolveRelatedHistograms()
    self.assertIsInstance(
        hist2.diagnostics.get('generic'), histogram.Generic)
    self.assertEqual(diag.value, hist2.diagnostics.get('generic').value)

  def testReplaceSharedDiagnostic(self):
    hist = histogram.Histogram('', 'unitless')
    hists = histogram_set.HistogramSet([hist])
    diag0 = histogram.Generic('shared0')
    diag1 = histogram.Generic('shared1')
    hists.AddSharedDiagnostic('generic0', diag0)
    hists.AddSharedDiagnostic('generic1', diag1)

    guid0 = diag0.guid
    guid1 = diag1.guid

    hists.ReplaceSharedDiagnostic(guid0, histogram.DiagnosticRef('fakeGuid'))

    self.assertEqual(hist.diagnostics['generic0'].guid, 'fakeGuid')
    self.assertEqual(hist.diagnostics['generic1'].guid, guid1)

  def testReplaceSharedDiagnostic_NonRefAddsToMap(self):
    hist = histogram.Histogram('', 'unitless')
    hists = histogram_set.HistogramSet([hist])
    diag0 = histogram.Generic('shared0')
    diag1 = histogram.Generic('shared1')
    hists.AddSharedDiagnostic('generic0', diag0)

    guid0 = diag0.guid
    guid1 = diag1.guid

    hists.ReplaceSharedDiagnostic(guid0, diag1)

    self.assertIsNotNone(hists.LookupDiagnostic(guid1))
