# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from tracing.value import histogram as histogram_module

class HistogramSet(object):
  def __init__(self, histograms=()):
    self._histograms_by_guid = {}
    self._shared_diagnostics_by_guid = {}
    for hist in histograms:
      self.AddHistogram(hist)

  @property
  def shared_diagnostics(self):
    return self._shared_diagnostics_by_guid.itervalues()

  def AddHistogram(self, hist, diagnostics=None):
    if hist.guid in self._histograms_by_guid:
      raise ValueError('Cannot add same Histogram twice')

    if diagnostics:
      for name, diagnostic in diagnostics.iteritems():
        hist.diagnostics[name] = diagnostic

    self._histograms_by_guid[hist.guid] = hist

  def AddSharedDiagnostic(self, name, diagnostic):
    self._shared_diagnostics_by_guid[diagnostic.guid] = diagnostic

    for hist in self:
      hist.diagnostics[name] = diagnostic

  def GetFirstHistogram(self):
    for histogram in self._histograms_by_guid.itervalues():
      return histogram

  def GetHistogramsNamed(self, name):
    return [h for h in self if h.name == name]

  def GetSharedDiagnosticsOfType(self, typ):
    return [d for d in self.shared_diagnostics if isinstance(d, typ)]

  def LookupHistogram(self, guid):
    return self._histograms_by_guid.get(guid)

  def LookupDiagnostic(self, guid):
    return self._shared_diagnostics_by_guid.get(guid)

  def ResolveRelatedHistograms(self):
    histograms = self
    def HandleDiagnosticMap(dm):
      for diagnostic in dm.itervalues():
        if isinstance(
            diagnostic, (histogram_module.RelatedHistogramSet,
                         histogram_module.RelatedHistogramMap)):
          diagnostic.Resolve(histograms)

    for hist in self:
      hist.diagnostics.ResolveSharedDiagnostics(self)
      HandleDiagnosticMap(hist.diagnostics)
      for dm in hist.nan_diagnostic_maps:
        HandleDiagnosticMap(dm)
      for hbin in hist.bins:
        for dm in hbin.diagnostic_maps:
          HandleDiagnosticMap(dm)

  def __len__(self):
    return len(self._histograms_by_guid)

  def __iter__(self):
    for hist in self._histograms_by_guid.itervalues():
      yield hist

  def ImportDicts(self, dicts):
    for d in dicts:
      if 'type' in d and d['type'] in histogram_module.Diagnostic.REGISTRY:
        diag = histogram_module.Diagnostic.FromDict(d)
        self._shared_diagnostics_by_guid[d['guid']] = diag
      else:
        self.AddHistogram(histogram_module.Histogram.FromDict(d))

  def AsDicts(self):
    dcts = []
    for d in self._shared_diagnostics_by_guid.itervalues():
      dcts.append(d.AsDict())
    for h in self:
      dcts.append(h.AsDict())
    return dcts

  def ReplaceSharedDiagnostic(self, old_guid, new_diagnostic):
    if not isinstance(new_diagnostic, histogram_module.DiagnosticRef):
      self._shared_diagnostics_by_guid[new_diagnostic.guid] = new_diagnostic

    for hist in self:
      for name, diagnostic in hist.diagnostics.iteritems():
        if diagnostic.has_guid and diagnostic.guid == old_guid:
          hist.diagnostics[name] = new_diagnostic
