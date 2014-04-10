// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('cc.picture_ops_list_view');
tvcm.require('cc.picture');
tvcm.require('tracing.importer.trace_event_importer');
tvcm.require('tracing.trace_model');
tvcm.requireRawScript('cc/layer_tree_host_impl_test_data.js');

tvcm.unittest.testSuite('cc.picture_ops_list_view_test', function() {
  var PictureOpsListView = cc.PictureOpsListView;

  test('instantiate', function() {
    if (!cc.PictureSnapshot.CanRasterize())
      return;
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = tvcm.dictionaryValues(m.processes)[0];

    var instance = p.objects.getAllInstancesNamed('cc::Picture')[0];
    var snapshot = instance.snapshots[0];

    var view = new PictureOpsListView();
    view.picture = snapshot;
    assertEquals(140, view.opsList_.children.length);
  });

  test('selection', function() {
    if (!cc.PictureSnapshot.CanRasterize())
      return;
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = tvcm.dictionaryValues(m.processes)[0];

    var instance = p.objects.getAllInstancesNamed('cc::Picture')[0];
    var snapshot = instance.snapshots[0];

    var view = new PictureOpsListView();
    view.picture = snapshot;
    var didSelectionChange = 0;
    view.addEventListener('selection-changed', function() {
      didSelectionChange = true;
    });
    assertFalse(didSelectionChange);
    view.opsList_.selectedElement = view.opsList_.children[3];
    assertTrue(didSelectionChange);
  });

});
