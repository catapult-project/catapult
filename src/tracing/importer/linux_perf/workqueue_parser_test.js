// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.linux_perf_importer');

base.unittest.testSuite('tracing.importer.linux_perf.workqueue_parser', function() { // @suppress longLineCheck
  test('workQueueImport', function() {
    var lines = [
      ' kworker/0:3-6880  [000]  2784.771958: workqueue_execute_start: ' +
                 'work struct ffff8800a5083a20: function intel_unpin_work_fn',
      ' kworker/0:3-6880  [000]  2784.771966: workqueue_execute_end: ' +
                 'work struct ffff8800a5083a20',
      ' kworker/1:2-7269  [001]  2784.805966: workqueue_execute_start: ' +
                 'work struct ffff88014fb0f158: function do_dbs_timer',
      ' kworker/1:2-7269  [001]  2784.805975: workqueue_execute_end: ' +
                 'work struct ffff88014fb0f158'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    assertEquals(1, m.processes['6880'].threads['6880'].sliceGroup.length);
    assertEquals(1, m.processes['7269'].threads['7269'].sliceGroup.length);
  });
});
