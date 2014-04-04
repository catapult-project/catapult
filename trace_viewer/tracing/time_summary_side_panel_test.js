// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.time_summary_side_panel');
tvcm.require('tracing.trace_model');

tvcm.unittest.testSuite('tracing.time_summary_side_panel_test', function() {
  function createModel() {
    var m = new tracing.TraceModel();
    m.importTraces([], false, false, function() {
      var browserProcess = m.getOrCreateProcess(1);
      var browserMain = browserProcess.getOrCreateThread(2);
      browserMain.name = 'CrBrowserMain';
      browserMain.sliceGroup.beginSlice('cat', 'Task', 0, undefined, 0);
      browserMain.sliceGroup.endSlice(10, 9);
      browserMain.sliceGroup.beginSlice('cat', 'Task', 20, undefined, 10);
      browserMain.sliceGroup.endSlice(30, 20);

      var rendererProcess = m.getOrCreateProcess(4);
      var rendererMain = rendererProcess.getOrCreateThread(5);
      rendererMain.name = 'CrRendererMain';
      rendererMain.sliceGroup.beginSlice('cat', 'Task', 0, undefined, 0);
      rendererMain.sliceGroup.endSlice(30, 25);
      rendererMain.sliceGroup.beginSlice('cat', 'Task', 40, undefined, 40);
      rendererMain.sliceGroup.endSlice(60, 50);
    });
    return m;
  }

  test('group', function() {
    var m = createModel();
    var group = new tracing.ResultsForGroup(m, 'foo');
    group.appendThreadSlices(m.bounds, m.processes[1].threads[2]);
    assertEquals(20, group.wallTime);
    assertEquals(19, group.cpuTime);
  });

  test('basic', function() {
    var m = createModel();
    assertTrue(tracing.TimeSummarySidePanel.supportsModel(m).supported);

    var panel = new tracing.TimeSummarySidePanel();
    panel.model = m;
    panel.style.border = '1px solid black';
    this.addHTMLOutput(panel);
  });
});
