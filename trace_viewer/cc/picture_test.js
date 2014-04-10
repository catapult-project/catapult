// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('cc');
tvcm.require('cc.picture');
tvcm.require('tracing.importer.trace_event_importer');
tvcm.require('tracing.trace_model');
tvcm.requireRawScript('cc/layer_tree_host_impl_test_data.js');

tvcm.unittest.testSuite('cc.picture_test', function() {
  test('basic', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = tvcm.dictionaryValues(m.processes)[0];

    var instance = p.objects.getAllInstancesNamed('cc::Picture')[0];
    var snapshot = instance.snapshots[0];

    assertTrue(snapshot instanceof cc.PictureSnapshot);
    instance.wasDeleted(150);
  });

  test('getOps', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = tvcm.dictionaryValues(m.processes)[0];

    var instance = p.objects.getAllInstancesNamed('cc::Picture')[0];
    var snapshot = instance.snapshots[0];

    var ops = snapshot.getOps();
    if (!ops)
      return;
    assertEquals(140, ops.length);

    var op0 = ops[0];
    assertEquals('Save', op0.cmd_string);
    assertTrue(op0.info instanceof Array);
  });
});
