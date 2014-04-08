// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.analysis.analysis_view');
tvcm.require('tracing.analysis.stub_analysis_results');
tvcm.require('tracing.analysis.analyze_counters');
tvcm.require('tracing.selection');
tvcm.require('tracing.trace_model.counter');
tvcm.require('tracing.trace_model.counter_series');

tvcm.unittest.testSuite('tracing.analysis.analyze_counters_test', function() {
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

    series.addCounterSample(0, 0);
    series.addCounterSample(10, 10);

    var selection = new Selection();
    var t1track = {};
    selection.push(ctr.getSeries(0).samples[1]);

    if (numSamples === 1)
      return selection;

    selection.push(ctr.getSeries(0).samples[0]);
    return selection;
  };

  function createSeries(ctr) {
    var allocatedSeries = new CounterSeries('bytesallocated', 0);
    var freeSeries = new CounterSeries('bytesfree', 1);

    ctr.addSeries(allocatedSeries);
    ctr.addSeries(freeSeries);

    allocatedSeries.addCounterSample(0, 0);
    allocatedSeries.addCounterSample(10, 25);
    allocatedSeries.addCounterSample(20, 10);

    freeSeries.addCounterSample(0, 15);
    freeSeries.addCounterSample(10, 20);
    freeSeries.addCounterSample(20, 5);
  }

  var createSelectionWithTwoSeriesSingleCounter = function() {
    var ctr = new Counter(null, 0, 'foo', 'ctr[0]');
    createSeries(ctr);

    var selection = new Selection();
    var t1track = {};

    selection.push(ctr.getSeries(0).samples[1]);
    selection.push(ctr.getSeries(1).samples[1]);
    return selection;
  };

  var createSelectionWithTwoSeriesTwoCounters = function() {
    var ctr1 = new Counter(null, 0, '', 'ctr1');
    createSeries(ctr1);

    var ctr2 = new Counter(null, 0, '', 'ctr2');
    createSeries(ctr2);

    var selection = new Selection();
    var t1track = {};

    selection.push(ctr1.getSeries(0).samples[1]);
    selection.push(ctr1.getSeries(1).samples[1]);


    selection.push(ctr2.getSeries(0).samples[2]);
    selection.push(ctr2.getSeries(1).samples[2]);
    return selection;
  };

  var createSelectionWithTwoCountersDiffSeriesDiffEvents = function() {
    var ctr1 = new Counter(null, 0, '', 'a');
    var ctr1AllocatedSeries = new CounterSeries('bytesallocated', 0);
    ctr1.addSeries(ctr1AllocatedSeries);

    ctr1AllocatedSeries.addCounterSample(0, 0);
    ctr1AllocatedSeries.addCounterSample(10, 25);
    ctr1AllocatedSeries.addCounterSample(20, 15);

    assertEquals('a', ctr1.name);
    assertEquals(3, ctr1.numSamples);
    assertEquals(1, ctr1.numSeries);

    var ctr2 = new Counter(null, 0, '', 'b');
    var ctr2AllocatedSeries = new CounterSeries('bytesallocated', 0);
    var ctr2FreeSeries = new CounterSeries('bytesfree', 1);

    ctr2.addSeries(ctr2AllocatedSeries);
    ctr2.addSeries(ctr2FreeSeries);

    ctr2AllocatedSeries.addCounterSample(0, 0);
    ctr2AllocatedSeries.addCounterSample(10, 25);
    ctr2AllocatedSeries.addCounterSample(20, 10);
    ctr2AllocatedSeries.addCounterSample(30, 15);

    ctr2FreeSeries.addCounterSample(0, 20);
    ctr2FreeSeries.addCounterSample(10, 5);
    ctr2FreeSeries.addCounterSample(20, 25);
    ctr2FreeSeries.addCounterSample(30, 0);

    assertEquals('b', ctr2.name);
    assertEquals(4, ctr2.numSamples);
    assertEquals(2, ctr2.numSeries);

    var selection = new Selection();
    var t1track = {};
    var t2track = {};

    selection.push(ctr1AllocatedSeries.samples[1]);
    selection.push(ctr2AllocatedSeries.samples[2]);
    selection.push(ctr2FreeSeries.samples[2]);

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
    assertEquals('Selected counter:', results.headers[0].label);
    var table = results.tables[0];
    assertEquals(3, table.rows.length);

    assertEquals('Title', table.rows[0].label);
    assertEquals('Timestamp', table.rows[1].label);
    assertEquals('value', table.rows[2].label);
    assertEquals(10, table.rows[2].text);
  });

  test('analyzeSelectionWithComplexSeriesTwoCounters', function() {
    var selection = createSelectionWithTwoCountersDiffSeriesDiffEvents();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(2, results.tables.length);
  });
});
