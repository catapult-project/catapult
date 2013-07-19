// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.analysis.analysis_view');
base.require('tracing.analysis.stub_analysis_results');
base.require('tracing.analysis.analyze_counters');
base.require('tracing.selection');
base.require('tracing.trace_model.counter');
base.require('tracing.trace_model.counter_series');

base.unittest.testSuite('tracing.analysis.analyze_counters', function() {
  var Counter = tracing.trace_model.Counter;
  var CounterSeries = tracing.trace_model.CounterSeries;

  var Selection = tracing.Selection;
  var AnalysisView = tracing.analysis.AnalysisView;
  var StubAnalysisResults = tracing.analysis.StubAnalysisResults;

  var createSelectionWithCounters = function(numSamples) {
    if (numSamples > 2 || numSamples < 1)
      throw new Error('This function only supports 1 or 2 samples');

    var ctr = new Counter(null, 0, '', 'ctr');
    var series = new CounterSeries('value', 0);
    ctr.addSeries(series);

    series.addSample(0, 0);
    series.addSample(10, 10);

    var selection = new Selection();
    var t1track = {};
    selection.addCounterSample(t1track, ctr, 1);

    if (numSamples === 1)
      return selection;

    selection.addCounterSample(t1track, ctr, 0);
    return selection;
  };

  function createSeries(ctr) {
    var allocatedSeries = new CounterSeries('bytesallocated', 0);
    var freeSeries = new CounterSeries('bytesfree', 1);

    ctr.addSeries(allocatedSeries);
    ctr.addSeries(freeSeries);

    allocatedSeries.addSample(0, 0);
    allocatedSeries.addSample(10, 25);
    allocatedSeries.addSample(20, 10);

    freeSeries.addSample(0, 15);
    freeSeries.addSample(10, 20);
    freeSeries.addSample(20, 5);
  }

  var createSelectionWithTwoSeriesSingleCounter = function() {
    var ctr = new Counter(null, 0, 'foo', 'ctr[0]');
    createSeries(ctr);

    var selection = new Selection();
    var t1track = {};

    selection.addCounterSample(t1track, ctr, 1);
    return selection;
  };

  var createSelectionWithTwoSeriesTwoCounters = function() {
    var ctr1 = new Counter(null, 0, '', 'ctr1');
    createSeries(ctr1);

    var ctr2 = new Counter(null, 0, '', 'ctr2');
    createSeries(ctr2);

    var selection = new Selection();
    var t1track = {};
    selection.addCounterSample(t1track, ctr1, 1);
    selection.addCounterSample(t1track, ctr2, 2);
    return selection;
  };

  var createSelectionWithTwoCountersDiffSeriesDiffHits = function() {
    var ctr1 = new Counter(null, 0, '', 'a');
    var allocatedSeries = new CounterSeries('bytesallocated', 0);
    ctr1.addSeries(allocatedSeries);

    allocatedSeries.addSample(0, 0);
    allocatedSeries.addSample(10, 25);
    allocatedSeries.addSample(20, 15);

    assertEquals('a', ctr1.name);
    assertEquals(3, ctr1.numSamples);
    assertEquals(1, ctr1.numSeries);

    var ctr2 = new Counter(null, 0, '', 'b');
    var allocatedSeries = new CounterSeries('bytesallocated', 0);
    var freeSeries = new CounterSeries('bytesfree', 1);

    ctr2.addSeries(allocatedSeries);
    ctr2.addSeries(freeSeries);

    allocatedSeries.addSample(0, 0);
    allocatedSeries.addSample(10, 25);
    allocatedSeries.addSample(20, 10);
    allocatedSeries.addSample(30, 15);

    freeSeries.addSample(0, 20);
    freeSeries.addSample(10, 5);
    freeSeries.addSample(20, 25);
    freeSeries.addSample(30, 0);

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

    assertEquals('ctr1: series(bytesallocated)', table.rows[0].label);
    assertEquals('ctr1: series(bytesfree)', table.rows[1].label);
    assertEquals('ctr2: series(bytesallocated)', table.rows[2].label);
    assertEquals('ctr2: series(bytesfree)', table.rows[3].label);
  });

  test('analyzeSelectionWithComplexSeriesTwoCounters', function() {
    var selection = createSelectionWithTwoCountersDiffSeriesDiffHits();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(1, results.tables.length);
    var table = results.tables[0];
    assertEquals('Counters:', table.tableHeader);
    assertEquals(3, table.rows.length);

    assertEquals('a: series(bytesallocated)', table.rows[0].label);
    assertEquals('b: series(bytesallocated)', table.rows[1].label);
    assertEquals('b: series(bytesfree)', table.rows[2].label);
  });
});
