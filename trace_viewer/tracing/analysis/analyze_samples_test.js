// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.analysis.analysis_view');
tvcm.require('tracing.analysis.stub_analysis_results');
tvcm.require('tracing.selection');
tvcm.require('tracing.trace_model');

tvcm.unittest.testSuite('tracing.analysis.analyze_samples_test', function() {
  var Model = tracing.TraceModel;
  var Selection = tracing.Selection;
  var AnalysisView = tracing.analysis.AnalysisView;
  var StubAnalysisResults = tracing.analysis.StubAnalysisResults;
  var newSampleNamed = tracing.test_utils.newSampleNamed;

  var createSelectionWithSingleSample = function() {
    var model = new Model();
    var t53;
    model.importTraces([], false, false, function() {
      t53 = model.getOrCreateProcess(52).getOrCreateThread(53);
      model.samples.push(newSampleNamed(t53, 'X', 'my-category',
                                        ['a', 'b', 'c'], 0.184));
    });

    var t53track = {};
    t53track.thread = t53;

    var selection = new Selection();

    assertEquals(0, selection.length);
    selection.push(t53.samples[0]);
    assertEquals(1, selection.length);

    return selection;
  };

  var createSelectionWithMultipleSamples = function() {
    var model = new Model();
    var t53;
    model.importTraces([], false, false, function() {
      t53 = model.getOrCreateProcess(52).getOrCreateThread(53);
      model.samples.push(newSampleNamed(t53, 'X', 'cat', ['BBB'], 0));
      model.samples.push(newSampleNamed(t53, 'X', 'cat', ['AAA'], 0.02));
      model.samples.push(newSampleNamed(t53, 'X', 'cat', ['AAA'], 0.04));
      model.samples.push(newSampleNamed(t53, 'X', 'cat', ['Sleeping'], 0.06));
      model.samples.push(newSampleNamed(t53, 'X', 'cat', ['BBB'], 0.08));
      model.samples.push(newSampleNamed(t53, 'X', 'cat', ['AAA'], 0.10));
      model.samples.push(newSampleNamed(t53, 'X', 'cat', ['CCC'], 0.12));
      model.samples.push(newSampleNamed(t53, 'X', 'cat', ['Sleeping'], 0.14));
    });

    var t53track = {};
    t53track.thread = t53;

    var selection = new Selection();
    for (var i = 0; i < t53.samples.length; i++)
      selection.push(t53.samples[i]);
    return selection;
  };

  test('instantiate_withSingleSample', function() {
    var selection = createSelectionWithSingleSample();

    var analysisEl = new AnalysisView();
    analysisEl.selection = selection;
    this.addHTMLOutput(analysisEl);
  });

  test('instantiate_withMultipleSamples', function() {
    var selection = createSelectionWithMultipleSamples();

    var analysisEl = new AnalysisView();
    this.addHTMLOutput(analysisEl);
    analysisEl.selection = selection;
  });

  test('analyzeSelectionWithSingleSample', function() {
    var selection = createSelectionWithSingleSample();

    var results = new StubAnalysisResults();
    tracing.analysis.analyzeSelection(results, selection);
    assertEquals(1, results.tables.length);
    var table = results.tables[0];
    var header = results.headers[0];
    assertEquals('Selected Sample Event:', header.label);
    assertEquals(3, table.rows.length);

    assertEquals('X', table.rows[0].text);
    assertEquals(0.184, table.rows[1].time);
    assertEquals('my-category: a', table.rows[2].text[0]);
    assertEquals('my-category: b', table.rows[2].text[1]);
    assertEquals('my-category: c', table.rows[2].text[2]);
  });
});
