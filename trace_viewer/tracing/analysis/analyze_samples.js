// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.requireStylesheet('tracing.analysis.analyze_slices');

tvcm.require('tracing.analysis.util');
tvcm.require('tvcm.ui');
tvcm.require('tvcm.ui.sortable_table');

tvcm.exportTo('tracing.analysis', function() {

  function analyzeSingleSampleEvent(results, sample, type) {
    results.appendHeader('Selected ' + type + ':');
    var table = results.appendTable('analysis-slice-table', 2);

    results.appendInfoRow(table, 'Title', sample.title);
    results.appendInfoRowTime(table, 'Sample Time', sample.start);
    results.appendInfoRow(table,
                          'Stack Trace',
                          sample.getUserFriendlyStackTrace());
  }

  function analyzeMultipleSampleEvents(results, slices, type) {
    // TODO (gholap): Move this to a new tab in analysis move.
    var panel = new tracing.SamplingSummaryPanel();
    results.appendChild(panel);
    panel.selection = slices;
  }

  return {
    analyzeMultipleSampleEvents: analyzeMultipleSampleEvents,
    analyzeSingleSampleEvent: analyzeSingleSampleEvent
  };
});
