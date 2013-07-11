// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.importer.linux_perf_importer');

base.unittest.testSuite('tracing.importer.linux_perf.kfunc_parser', function() {
  test('kernelFunctionParser', function() {
    var lines = [
      'Binder_2-127  ( 127) [001] ....  3431.906759: graph_ent: func=sys_write',
      'Binder_2-127  ( 127) [001] ....  3431.906769: graph_ret: func=sys_write',
      'Binder_2-127  ( 127) [001] ....  3431.906785: graph_ent: func=sys_write',
      'Binder_2-127  ( 127) [001] ...1  3431.906798: tracing_mark_write: B|' +
          '127|dequeueBuffer',
      'Binder_2-127  ( 127) [001] ....  3431.906802: graph_ret: func=sys_write',
      'Binder_2-127  ( 127) [001] ....  3431.906842: graph_ent: func=sys_write',
      'Binder_2-127  ( 127) [001] ...1  3431.906849: tracing_mark_write: E',
      'Binder_2-127  ( 127) [001] ....  3431.906853: graph_ret: func=sys_write',
      'Binder_2-127  ( 127) [001] ....  3431.906896: graph_ent: func=sys_write',
      'Binder_2-127  ( 127) [001] ....  3431.906906: graph_ret: func=sys_write'
    ];
    var m = new tracing.TraceModel(lines.join('\n'), false);
    assertEquals(0, m.importErrors.length);

    var process = m.processes[127];
    assertNotNull(process);

    var thread = process.threads[127];
    assertNotNull(thread);

    var slices = thread.sliceGroup.slices;
    assertEquals(7, thread.sliceGroup.length);

    // Slice 0 is an un-split sys_write
    assertEquals('sys_write', slices[0].title);

    // Slices 1 & 2 are a split sys_write
    assertEquals('sys_write', slices[1].title);
    assertEquals('sys_write (cont.)', slices[2].title);

    // Slices 3 & 5 are a split sys_write with the dequeueBuffer in between
    assertEquals('sys_write', slices[3].title);
    assertEquals('dequeueBuffer', slices[4].title);
    assertEquals('sys_write (cont.)', slices[5].title);

    // Slice 6 is another un-split sys_write
    assertEquals('sys_write', slices[6].title);
  });
});
