// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.analysis.analysis_view');
tvcm.require('tracing.analysis.stub_analysis_results');
tvcm.require('tracing.selection');
tvcm.require('tracing.trace_model');

tvcm.unittest.testSuite('tracing.analysis.analyze_slices_test', function() {
  var Model = tracing.TraceModel;
  var Thread = tracing.trace_model.Thread;
  var Selection = tracing.Selection;
  var AnalysisView = tracing.analysis.AnalysisView;
  var StubAnalysisResults = tracing.analysis.StubAnalysisResults;
  var newSliceNamed = tracing.test_utils.newSliceNamed;
  var newSampleNamed = tracing.test_utils.newSampleNamed;
  var newSliceCategory = tracing.test_utils.newSliceCategory;

  var createSelectionWithSingleSlice = function(withCategory) {
    var model = new Model();
    var t53 = model.getOrCreateProcess(52).getOrCreateThread(53);
    if (withCategory)
      t53.sliceGroup.pushSlice(newSliceCategory('foo', 'b', 0, 0.002));
    else
      t53.sliceGroup.pushSlice(newSliceNamed('b', 0, 0.002));

    var t53track = {};
    t53track.thread = t53;

    var selection = new Selection();
    selection.push(t53.sliceGroup.slices[0]);
    assertEquals(1, selection.length);

    return selection;
  };

  var createSelectionWithTwoSlices = function() {
    var model = new Model();
    var t53 = model.getOrCreateProcess(52).getOrCreateThread(53);
    t53.sliceGroup.pushSlice(newSliceNamed('a', 0.0, 0.04));
    t53.sliceGroup.pushSlice(newSliceNamed('aa', 0.120, 0.06));

    var t53track = {};
    t53track.thread = t53;

    var selection = new Selection();
    selection.push(t53.sliceGroup.slices[0]);
    selection.push(t53.sliceGroup.slices[1]);

    return selection;
  };

  var createSelectionWithTwoSlicesSameTitle = function() {
    var model = new Model();
    var t53 = model.getOrCreateProcess(52).getOrCreateThread(53);
    t53.sliceGroup.pushSlice(newSliceNamed('c', 0.0, 0.04));
    t53.sliceGroup.pushSlice(newSliceNamed('c', 0.12, 0.06));

    var t53track = {};
    t53track.thread = t53;

    var selection = new Selection();
    selection.push(t53.sliceGroup.slices[0]);
    selection.push(t53.sliceGroup.slices[1]);

    return selection;
  };

  var createSelectionWithSamples = function() {
    var model = new Model();
    var t53;
    model.importTraces([], false, false, function() {
      t53 = model.getOrCreateProcess(52).getOrCreateThread(53);
      model.samples.push(newSampleNamed(t53, 'X', 'BBB', 0));
      model.samples.push(newSampleNamed(t53, 'X', 'AAA', 0.02));
      model.samples.push(newSampleNamed(t53, 'X', 'AAA', 0.04));
      model.samples.push(newSampleNamed(t53, 'X', 'Sleeping', 0.06));
      model.samples.push(newSampleNamed(t53, 'X', 'BBB', 0.08));
      model.samples.push(newSampleNamed(t53, 'X', 'AAA', 0.10));
      model.samples.push(newSampleNamed(t53, 'X', 'CCC', 0.12));
      model.samples.push(newSampleNamed(t53, 'X', 'Sleeping', 0.14));
    });

    var t53track = {};
    t53track.thread = t53;

    var selection = new Selection();
    for (var i = 0; i < t53.samples.length; i++)
      selection.push(t53.samples[i]);
    return selection;
  };

  test('instantiate_withSingleSlice', function() {
    var selection = createSelectionWithSingleSlice();

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });

  test('instantiate_withSingleSliceCategory', function() {
    var selection = createSelectionWithSingleSlice(true);

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });

  test('instantiate_withMultipleSlices', function() {
    var selection = createSelectionWithTwoSlices();

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });

  test('instantiate_withMultipleSlicesSameTitle', function() {
    var selection = createSelectionWithTwoSlicesSameTitle();

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });

  test('instantiate_withMultipleSamples', function() {
    var selection = createSelectionWithSamples();

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });

  test('analyzeSelectionWithSingleSlice', function() {
    var selection = createSelectionWithSingleSlice();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(1, results.tables.length);
    var table = results.tables[0];
    var header = results.headers[0];
    assertEquals('Selected Slice:', header.label);
    assertEquals(3, table.rows.length);

    assertEquals('b', table.rows[0].text);
    assertEquals(0, table.rows[1].time);
    assertAlmostEquals(0.002, table.rows[2].time);
  });

  test('analyzeSelectionWithSingleSliceCategory', function() {
    var selection = createSelectionWithSingleSlice(true);

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(1, results.tables.length);
    var table = results.tables[0];
    var header = results.headers[0];
    assertEquals('Selected Slice:', header.label);
    assertEquals(4, table.rows.length);

    assertEquals('b', table.rows[0].text);
    assertEquals('foo', table.rows[1].text);
    assertEquals(0, table.rows[2].time);
    assertAlmostEquals(0.002, table.rows[3].time);
  });

  test('analyzeSelectionWithTwoSlices', function() {
    var selection = createSelectionWithTwoSlices();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(1, results.tables.length);
    var table = results.tables[0];
    assertEquals('Slices:', results.headers[0].label);
    assertEquals(6, table.rows.length);

    assertEquals('a', table.rows[0].label);
    assertEquals(1, table.rows[0].occurences);
    assertAlmostEquals(0.04, table.rows[0].duration);
    assertAlmostEquals(0.04, table.rows[0].selfTime);
    assertEquals(null, table.rows[0].cpuDuration);
    assertEquals('aa', table.rows[1].label);
    assertEquals(1, table.rows[1].occurences);
    assertAlmostEquals(0.06, table.rows[1].duration);
    assertAlmostEquals(0.06, table.rows[1].selfTime);
    assertEquals(null, table.rows[1].cpuDuration);
    assertEquals('Totals', table.rows[2].label);
    assertEquals(2, table.rows[2].occurences);
    assertAlmostEquals(0.1, table.rows[2].duration);
    assertAlmostEquals(0.1, table.rows[2].selfTime);
    assertEquals(null, table.rows[2].cpuDuration);

    assertEquals('Selection start', table.rows[4].label);
    assertAlmostEquals(0, table.rows[4].time);

    assertEquals('Selection extent', table.rows[5].label);
    assertAlmostEquals(0.18, table.rows[5].time);
  });

  test('analyzeSelectionWithTwoSlicesSameTitle', function() {
    var selection = createSelectionWithTwoSlicesSameTitle();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(2, results.tables.length);

    var t;
    assertEquals('Slices:', results.headers[0].label);
    // Table 1.
    t = results.tables[0];
    assertObjectEquals({
      label: 'c',
      duration: 0.1,
      cpuDuration: null,
      selfTime: 0.1,
      cpuSelfTime: null,
      occurences: 2,
      percentage: null,
      details: {
        min: 0.04, max: 0.06, avg: 0.05,
        avg_stddev: 0.014142135623730947
      }
    }, t.rows[0]);

    assertObjectEquals({label: 'Selection start', time: 0}, t.rows[1]);
    assertObjectEquals({label: 'Selection extent', time: 0.18}, t.rows[2]);

    assertObjectEquals({label: 'Title: ', value: 'c'}, results.info[0]);
    assertObjectEquals({label: 'Category: ', value: ''}, results.info[1]);

    // Table 2.
    var t = results.tables[1];
    assertObjectEquals(
        {start: 0,
          duration: 0.04,
          selfTime: 0.04,
          args: {}
        },
        t.rows[0]);
    assertObjectEquals(
        {start: 0.12,
          duration: 0.06,
          selfTime: 0.06,
          args: {}
        },
        t.rows[1]);
  });

  test('analyzeSelectionWithSamples', function() {
    var selection = createSelectionWithSamples();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    console.log(results.tables);
    assertEquals(1, results.tables.length);

    assertEquals('Sample Events:', results.headers[0].label);

    var table = results.tables[0];
    assertObjectEquals({
      label: 'AAA',
      duration: null,
      cpuDuration: null,
      selfTime: null,
      cpuSelfTime: null,
      occurences: 3,
      percentage: '50%',
      details: null
    }, table.rows[0]);

    assertObjectEquals({
      label: 'BBB',
      duration: null,
      cpuDuration: null,
      selfTime: null,
      cpuSelfTime: null,
      occurences: 2,
      percentage: '33.333%',
      details: null
    }, table.rows[1]);

    assertObjectEquals({
      label: 'CCC',
      duration: null,
      cpuDuration: null,
      selfTime: null,
      cpuSelfTime: null,
      occurences: 1,
      percentage: '16.667%',
      details: null
    }, table.rows[2]);

    assertObjectEquals({
      label: 'Sleeping',
      duration: null,
      cpuDuration: null,
      selfTime: null,
      cpuSelfTime: null,
      occurences: 2,
      percentage: '-',
      details: null
    }, table.rows[3]);
  });

  test('instantiate_withSingleSliceContainingIDRef', function() {
    var model = new Model();
    var p1 = model.getOrCreateProcess(1);
    var myObjectSlice = p1.objects.addSnapshot(
        '0x1000', 'cat', 'my_object', 0);

    var t1 = p1.getOrCreateThread(1);
    t1.sliceGroup.pushSlice(newSliceCategory('cat', 'b', 0, 2));
    t1.sliceGroup.slices[0].args.my_object = myObjectSlice;

    var t1track = {};
    t1track.thread = t1;

    var selection = new Selection();
    selection.push(t1.sliceGroup.slices[0]);
    assertEquals(1, selection.length);

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });
});
