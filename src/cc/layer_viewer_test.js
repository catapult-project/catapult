// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('cc');
base.require('cc.layer_viewer');
base.require('tracing.importer.trace_event_importer');
base.require('tracing.trace_model');
base.require('cc.layer_tree_host_impl_test_data');

base.unittest.testSuite('cc.layer_viewer', function() {
  test('instantiate', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = m.processes[1];

    var instance = p.objects.getAllInstancesNamed('cc::LayerTreeHostImpl')[0];
    var lthi = instance.snapshots[0];
    var layer = lthi.activeTree.renderSurfaceLayerList[0];

    var viewer = new cc.LayerViewer();
    viewer.style.height = '500px';
    viewer.layerTreeImpl = lthi.activeTree;
    viewer.selection = new cc.LayerSelection(layer);

    this.addHTMLOutput(viewer);
  });

  test('instantiate_withTileHighlight', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = m.processes[1];

    var instance = p.objects.getAllInstancesNamed('cc::LayerTreeHostImpl')[0];
    var lthi = instance.snapshots[0];
    var layer = lthi.activeTree.renderSurfaceLayerList[0];
    var tile = lthi.tiles[0];

    var viewer = new cc.LayerViewer();
    viewer.style.height = '500px';
    viewer.layerTreeImpl = lthi.activeTree;
    viewer.selection = new cc.TileSelection(tile);
    this.addHTMLOutput(viewer);
  });
});
