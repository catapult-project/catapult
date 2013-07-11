// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.analysis.analysis_view');
base.require('tracing.analysis.stub_analysis_results');
base.require('tracing.selection');
base.require('tracing.trace_model');

base.unittest.testSuite('tracing.analysis.analyze_slices', function() {
  var Model = tracing.TraceModel;
  var Thread = tracing.trace_model.Thread;
  var Selection = tracing.Selection;
  var AnalysisView = tracing.analysis.AnalysisView;
  var StubAnalysisResults = tracing.analysis.StubAnalysisResults;
  var newSliceNamed = tracing.test_utils.newSliceNamed;
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
    selection.addSlice(t53track, t53.sliceGroup.slices[0]);
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
    selection.addSlice(t53track, t53.sliceGroup.slices[0]);
    selection.addSlice(t53track, t53.sliceGroup.slices[1]);

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
    selection.addSlice(t53track, t53.sliceGroup.slices[0]);
    selection.addSlice(t53track, t53.sliceGroup.slices[1]);

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

  test('analyzeSelectionWithSingleSlice', function() {
    var selection = createSelectionWithSingleSlice();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(1, results.tables.length);
    var table = results.tables[0];
    assertEquals('Selected slice:', table.tableHeader);
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
    assertEquals('Selected slice:', table.tableHeader);
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
    assertEquals('Slices:', table.tableHeader);
    assertEquals(6, table.rows.length);

    assertEquals('a', table.rows[0].label);
    assertEquals(1, table.rows[0].occurences);
    assertAlmostEquals(0.04, table.rows[0].duration);
    assertEquals('aa', table.rows[1].label);
    assertEquals(1, table.rows[1].occurences);
    assertAlmostEquals(0.06, table.rows[1].duration);
    assertEquals('*Totals', table.rows[2].label);
    assertEquals(2, table.rows[2].occurences);
    assertAlmostEquals(0.1, table.rows[2].duration);

    assertEquals('Selection start', table.rows[4].label);
    assertAlmostEquals(0, table.rows[4].time);

    assertEquals('Selection extent', table.rows[5].label);
    assertAlmostEquals(0.18, table.rows[5].time);
  });

  test('analyzeSelectionWithTwoSlicesSameTitle', function() {
    var selection = createSelectionWithTwoSlicesSameTitle();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(3, results.tables.length);

    var t;
    // Table 1.
    t = results.tables[0];
    assertEquals('Slices:', t.tableHeader);
    assertObjectEquals(
        {label: 'c',
          duration: 0.1,
          occurences: 2,
          details: {min: 0.04, max: 0.06, avg: 0.05,
            avg_stddev: 0.014142135623730947}
        },
        t.rows[0]);
    assertObjectEquals({label: 'Selection start', time: 0}, t.rows[1]);
    assertObjectEquals({label: 'Selection extent', time: 0.18}, t.rows[2]);

    // Table 2.
    var t = results.tables[1];
    assertObjectEquals({label: 'Title', text: 'c'}, t.rows[0]);
    assertObjectEquals({label: 'Start', time: 0}, t.rows[1]);
    assertObjectEquals({label: 'Duration', time: 0.04}, t.rows[2]);

    // Table 3.
    var t = results.tables[2];
    assertObjectEquals({label: 'Title', text: 'c'}, t.rows[0]);
    assertObjectEquals({label: 'Start', time: 0.12}, t.rows[1]);
    assertObjectEquals({label: 'Duration', time: 0.06}, t.rows[2]);
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
    selection.addSlice(t1track, t1.sliceGroup.slices[0]);
    assertEquals(1, selection.length);

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });
});
