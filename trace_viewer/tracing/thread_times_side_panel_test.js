// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.thread_times_side_panel');
tvcm.require('tracing.trace_model');

tvcm.unittest.testSuite('tracing.thread_times_side_panel_test', function() {
  test('basic', function() {
    var m = new tracing.TraceModel();
    m.importTraces([], false, false, function() {
      var browserProcess = m.getOrCreateProcess(1);
      var browserMain = browserProcess.getOrCreateThread(2);
      browserMain.sliceGroup.beginSlice('cat', 'Task', 0);
      browserMain.sliceGroup.endSlice(10);
      browserMain.sliceGroup.beginSlice('cat', 'Task', 20);
      browserMain.sliceGroup.endSlice(30);
    });

    assertTrue(tracing.ThreadTimesSidePanel.supportsModel(m).supported);

    var panel = new tracing.ThreadTimesSidePanel();
    panel.model = m;
    panel.style.border = '1px solid black';
    this.addHTMLOutput(panel);
  });
});
