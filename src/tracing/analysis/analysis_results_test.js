// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.analysis.analysis_results');
base.require('tracing.selection');

'use strict';

base.unittest.testSuite('tracing.analysis.analysis_results', function() {
  test('selectionChangingLink', function() {
    var r = tracing.analysis.AnalysisResults();
    var track = {};
    var linkEl = r.createSelectionChangingLink('hello', function() {
      var selection = new tracing.Selection();
      selection.addSlice(track, {});
      return selection;
    });
    var didRequestSelectionChange = false;
    linkEl.addEventListener('requestSelectionChange', function(e) {
      didRequestSelectionChange = true;
    });
    linkEl.click();
    assertTrue(didRequestSelectionChange);
  });
});
