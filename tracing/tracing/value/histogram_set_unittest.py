# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from tracing.value import histogram
from tracing.value import histogram_set
from tracing.value.diagnostics import date_range
from tracing.value.diagnostics import diagnostic_ref
from tracing.value.diagnostics import generic_set

class HistogramSetUnittest(unittest.TestCase):

  def testGetSharedDiagnosticsOfType(self):
    d0 = generic_set.GenericSet(['foo'])
    d1 = date_range.DateRange(0)
    hs = histogram_set.HistogramSet()
    hs.AddSharedDiagnosticToAllHistograms('generic', d0)
    hs.AddSharedDiagnosticToAllHistograms('generic', d1)
    diagnostics = hs.GetSharedDiagnosticsOfType(generic_set.GenericSet)
    self.assertEqual(len(diagnostics), 1)
    self.assertIsInstance(diagnostics[0], generic_set.GenericSet)

  def testImportDicts(self):
    hist = histogram.Histogram('', 'unitless')
    hists = histogram_set.HistogramSet([hist])
    hists2 = histogram_set.HistogramSet()
    hists2.ImportDicts(hists.AsDicts())
    self.assertEqual(len(hists), len(hists2))

  def testAssertType(self):
    hs = histogram_set.HistogramSet()
    with self.assertRaises(AssertionError):
      hs.ImportDicts([{'type': ''}])

  def testFilterHistogram(self):
    a = histogram.Histogram('a', 'unitless')
    b = histogram.Histogram('b', 'unitless')
    c = histogram.Histogram('c', 'unitless')
    hs = histogram_set.HistogramSet([a, b, c])
    hs.FilterHistograms(lambda h: h.name == 'b')

    names = set(['a', 'c'])
    for h in hs:
      self.assertIn(h.name, names)
      names.remove(h.name)
    self.assertEqual(0, len(names))

  def testRemoveOrphanedDiagnostics(self):
    da = generic_set.GenericSet(['a'])
    db = generic_set.GenericSet(['b'])
    a = histogram.Histogram('a', 'unitless')
    b = histogram.Histogram('b', 'unitless')
    hs = histogram_set.HistogramSet([a])
    hs.AddSharedDiagnosticToAllHistograms('a', da)
    hs.AddHistogram(b)
    hs.AddSharedDiagnosticToAllHistograms('b', db)
    hs.FilterHistograms(lambda h: h.name == 'a')

    dicts = hs.AsDicts()
    self.assertEqual(3, len(dicts))

    hs.RemoveOrphanedDiagnostics()
    dicts = hs.AsDicts()
    self.assertEqual(2, len(dicts))

  def testAddSharedDiagnostic(self):
    diags = {}
    da = generic_set.GenericSet(['a'])
    db = generic_set.GenericSet(['b'])
    diags['da'] = da
    diags['db'] = db
    a = histogram.Histogram('a', 'unitless')
    b = histogram.Histogram('b', 'unitless')
    hs = histogram_set.HistogramSet()
    hs.AddSharedDiagnostic(da)
    hs.AddHistogram(a, {'da': da})
    hs.AddHistogram(b, {'db': db})

    # This should produce one shared diagnostic and 2 histograms.
    dicts = hs.AsDicts()
    self.assertEqual(3, len(dicts))
    self.assertEqual(da.AsDict(), dicts[0])


    # Assert that you only see the shared diagnostic once.
    seen_once = False
    for idx, val in enumerate(dicts):
      if idx == 0:
        continue
      if 'da' in val['diagnostics']:
        self.assertFalse(seen_once)
        self.assertEqual(val['diagnostics']['da'], da.guid)
        seen_once = True


  def testSharedDiagnostic(self):
    hist = histogram.Histogram('', 'unitless')
    hists = histogram_set.HistogramSet([hist])
    diag = generic_set.GenericSet(['shared'])
    hists.AddSharedDiagnosticToAllHistograms('generic', diag)

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

    self.assertIsInstance(
        hist2.diagnostics.get('generic'), generic_set.GenericSet)
    self.assertEqual(list(diag), list(hist2.diagnostics.get('generic')))

  def testReplaceSharedDiagnostic(self):
    hist = histogram.Histogram('', 'unitless')
    hists = histogram_set.HistogramSet([hist])
    diag0 = generic_set.GenericSet(['shared0'])
    diag1 = generic_set.GenericSet(['shared1'])
    hists.AddSharedDiagnosticToAllHistograms('generic0', diag0)
    hists.AddSharedDiagnosticToAllHistograms('generic1', diag1)

    guid0 = diag0.guid
    guid1 = diag1.guid

    hists.ReplaceSharedDiagnostic(
        guid0, diagnostic_ref.DiagnosticRef('fakeGuid'))

    self.assertEqual(hist.diagnostics['generic0'].guid, 'fakeGuid')
    self.assertEqual(hist.diagnostics['generic1'].guid, guid1)

  def testReplaceSharedDiagnostic_NonRefAddsToMap(self):
    hist = histogram.Histogram('', 'unitless')
    hists = histogram_set.HistogramSet([hist])
    diag0 = generic_set.GenericSet(['shared0'])
    diag1 = generic_set.GenericSet(['shared1'])
    hists.AddSharedDiagnosticToAllHistograms('generic0', diag0)

    guid0 = diag0.guid
    guid1 = diag1.guid

    hists.ReplaceSharedDiagnostic(guid0, diag1)

    self.assertIsNotNone(hists.LookupDiagnostic(guid1))

  def testDeduplicateDiagnostics(self):
    generic_a = generic_set.GenericSet(['A'])
    generic_b = generic_set.GenericSet(['B'])
    date_a = date_range.DateRange(42)
    date_b = date_range.DateRange(57)

    a_hist = histogram.Histogram('a', 'unitless')
    generic0 = generic_set.GenericSet.FromDict(generic_a.AsDict())
    generic0.AddDiagnostic(generic_b)
    a_hist.diagnostics['generic'] = generic0
    date0 = date_range.DateRange.FromDict(date_a.AsDict())
    date0.AddDiagnostic(date_b)
    a_hist.diagnostics['date'] = date0

    b_hist = histogram.Histogram('b', 'unitless')
    generic1 = generic_set.GenericSet.FromDict(generic_a.AsDict())
    generic1.AddDiagnostic(generic_b)
    b_hist.diagnostics['generic'] = generic1
    date1 = date_range.DateRange.FromDict(date_a.AsDict())
    date1.AddDiagnostic(date_b)
    b_hist.diagnostics['date'] = date1

    c_hist = histogram.Histogram('c', 'unitless')
    c_hist.diagnostics['generic'] = generic1

    histograms = histogram_set.HistogramSet([a_hist, b_hist, c_hist])
    self.assertNotEqual(
        a_hist.diagnostics['generic'].guid, b_hist.diagnostics['generic'].guid)
    self.assertEqual(
        b_hist.diagnostics['generic'].guid, c_hist.diagnostics['generic'].guid)
    self.assertEqual(
        a_hist.diagnostics['generic'], b_hist.diagnostics['generic'])
    self.assertNotEqual(
        a_hist.diagnostics['date'].guid, b_hist.diagnostics['date'].guid)
    self.assertEqual(
        a_hist.diagnostics['date'], b_hist.diagnostics['date'])

    histograms.DeduplicateDiagnostics()

    self.assertEqual(
        a_hist.diagnostics['generic'].guid, b_hist.diagnostics['generic'].guid)
    self.assertEqual(
        b_hist.diagnostics['generic'].guid, c_hist.diagnostics['generic'].guid)
    self.assertEqual(
        a_hist.diagnostics['generic'], b_hist.diagnostics['generic'])
    self.assertEqual(
        a_hist.diagnostics['date'].guid, b_hist.diagnostics['date'].guid)
    self.assertEqual(
        a_hist.diagnostics['date'], b_hist.diagnostics['date'])

    histogram_dicts = histograms.AsDicts()

    # All diagnostics should have been serialized as DiagnosticRefs.
    for d in histogram_dicts:
      if 'type' not in d:
        for diagnostic_dict in d['diagnostics'].values():
          self.assertIsInstance(diagnostic_dict, str)

    histograms2 = histogram_set.HistogramSet()
    histograms2.ImportDicts(histograms.AsDicts())
    a_hists = histograms2.GetHistogramsNamed('a')
    self.assertEqual(len(a_hists), 1)
    a_hist2 = a_hists[0]
    b_hists = histograms2.GetHistogramsNamed('b')
    self.assertEqual(len(b_hists), 1)
    b_hist2 = b_hists[0]

    self.assertEqual(
        a_hist2.diagnostics['generic'].guid,
        b_hist2.diagnostics['generic'].guid)
    self.assertEqual(
        a_hist2.diagnostics['generic'],
        b_hist2.diagnostics['generic'])
    self.assertEqual(
        a_hist2.diagnostics['date'].guid,
        b_hist2.diagnostics['date'].guid)
    self.assertEqual(
        a_hist2.diagnostics['date'],
        b_hist2.diagnostics['date'])
