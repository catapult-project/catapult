// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('tracing.analysis.analysis_view');
base.require('tracing.analysis.stub_analysis_results');
base.require('tracing.analysis.analyze_counters');
base.require('tracing.selection');
base.require('tracing.trace_model');

'use strict';

base.unittest.testSuite('tracing.analysis.analyze_counters', function() {
  var Counter = tracing.trace_model.Counter;
  var Model = tracing.TraceModel;
  var Thread = tracing.trace_model.Thread;
  var Selection = tracing.Selection;
  var AnalysisView = tracing.analysis.AnalysisView;
  var StubAnalysisResults = tracing.analysis.StubAnalysisResults;

  var createSelectionWithCounters = function(numSamples) {
    if (numSamples > 2 || numSamples < 1)
      throw new Error('This function only supports 1 or 2 samples');
    var ctr = new Counter(null, 0, '', 'ctr');
    ctr.seriesNames.push('value');
    ctr.seriesColors.push(0);
    ctr.timestamps.push(0, 10);
    ctr.samples.push(0, 10);

    var selection = new Selection();
    var t1track = {};
    selection.addCounterSample(t1track, ctr, 1);

    if (numSamples == 1)
      return selection;

    selection.addCounterSample(t1track, ctr, 0);
    return selection;
  };

  var createSelectionWithTwoSeriesSingleCounter = function() {
    var ctr = new Counter(null, 0, 'foo', 'ctr[0]');
    ctr.seriesNames.push('bytesallocated', 'bytesfree');
    ctr.seriesColors.push(0, 1);
    ctr.timestamps.push(0, 10, 20);
    ctr.samples.push(0, 25, 10, 15, 20, 5);

    var selection = new Selection();
    var t1track = {};

    selection.addCounterSample(t1track, ctr, 1);
    return selection;
  };

  var createSelectionWithTwoSeriesTwoCounters = function() {
    var ctr1 = new Counter(null, 0, '', 'ctr1');
    ctr1.seriesNames.push('bytesallocated', 'bytesfree');
    ctr1.seriesColors.push(0, 1);
    ctr1.timestamps.push(0, 10, 20);
    ctr1.samples.push(0, 25, 10, 15, 20, 5);

    var ctr2 = new Counter(null, 0, '', 'ctr2');
    ctr2.seriesNames.push('bytesallocated', 'bytesfree');
    ctr2.seriesColors.push(0, 1);
    ctr2.timestamps.push(0, 10, 20);
    ctr2.samples.push(0, 25, 10, 15, 20, 5);

    var selection = new Selection();
    var t1track = {};
    selection.addCounterSample(t1track, ctr1, 1);
    selection.addCounterSample(t1track, ctr2, 2);
    return selection;
  };

  var createSelectionWithTwoCountersDiffSeriesDiffHits = function() {
    var ctr1 = new Counter(null, 0, '', 'a');
    ctr1.seriesNames.push('bytesallocated');
    ctr1.seriesColors.push(0);
    ctr1.timestamps.push(0, 10, 20);
    ctr1.samples.push(0, 25, 10);
    assertEquals('a', ctr1.name);
    assertEquals(3, ctr1.numSamples);
    assertEquals(1, ctr1.numSeries);

    var ctr2 = new Counter(null, 0, '', 'b');
    ctr2.seriesNames.push('bytesallocated', 'bytesfree');
    ctr2.seriesColors.push(0, 1);
    ctr2.timestamps.push(0, 10, 20, 30);
    ctr2.samples.push(0, 25, 10, 15, 20, 5, 25, 0);
    assertEquals('b', ctr2.name);
    assertEquals(4, ctr2.numSamples);
    assertEquals(2, ctr2.numSeries);

    var selection = new Selection();
    var t1track = {};
    selection.addCounterSample(t1track, ctr1, 1);
    selection.addCounterSample(t1track, ctr2, 2);

    return selection;
  };

  test('instantiate_singleCounterWithTwoSeries', function() {
    var selection = createSelectionWithTwoSeriesSingleCounter();

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });

  test('instantiate_twoCountersWithTwoSeries', function() {
    var selection = createSelectionWithTwoSeriesTwoCounters();

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });

  test('analyzeSelectionWithSingleCounter', function() {
    var selection = createSelectionWithCounters(1);

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(1, results.tables.length);
    var table = results.tables[0];
    assertEquals('Selected counter:', table.tableHeader);
    assertEquals(3, table.rows.length);

    assertEquals('Title', table.rows[0].label);
    assertEquals('Timestamp', table.rows[1].label);
    assertEquals('value', table.rows[2].label);
    assertEquals(10, table.rows[2].text);
  });

  test('analyzeSelectionWithBasicTwoSeriesTwoCounters', function() {
    var selection = createSelectionWithTwoSeriesTwoCounters();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(1, results.tables.length);
    var table = results.tables[0];
    assertEquals('Counters:', table.tableHeader);
    assertEquals(4, table.rows.length);

    assertEquals('ctr1: bytesallocated', table.rows[0].label);
    assertEquals('ctr1: bytesfree', table.rows[1].label);
    assertEquals('ctr2: bytesallocated', table.rows[2].label);
    assertEquals('ctr2: bytesfree', table.rows[3].label);
  });

  test('analyzeSelectionWithComplexSeriesTwoCounters', function() {
    var selection = createSelectionWithTwoCountersDiffSeriesDiffHits();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(1, results.tables.length);
    var table = results.tables[0];
    assertEquals('Counters:', table.tableHeader);
    assertEquals(3, table.rows.length);

    assertEquals('a: bytesallocated', table.rows[0].label);
    assertEquals('b: bytesallocated', table.rows[1].label);
    assertEquals('b: bytesfree', table.rows[2].label);
  });
});
