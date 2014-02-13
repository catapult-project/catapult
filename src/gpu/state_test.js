// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('gpu');
tvcm.require('gpu.state');
tvcm.require('tracing.importer.trace_event_importer');
tvcm.require('tracing.trace_model');
tvcm.requireRawScript('gpu/state_test_data.js');

tvcm.unittest.testSuite('gpu.state_test', function() {
  test('basic', function() {
    var m = new tracing.TraceModel(g_gpu_state_trace);
    var p = tvcm.dictionaryValues(m.processes)[0];

    var instance = p.objects.getAllInstancesNamed('gpu::State')[0];
    var snapshot = instance.snapshots[0];

    assertTrue(snapshot instanceof gpu.StateSnapshot);
    assertEquals(typeof(snapshot.screenshot), 'string');
    instance.wasDeleted(150);
  });
});
