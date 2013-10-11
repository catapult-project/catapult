// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('cc');
base.require('cc.layer_view');
base.require('tracing.importer.trace_event_importer');
base.require('tracing.trace_model');
base.require('cc.layer_tree_host_impl_test_data');

base.unittest.testSuite('cc.layer_view', function() {
  test('instantiate', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = m.processes[1];

    var instance = p.objects.getAllInstancesNamed('cc::LayerTreeHostImpl')[0];
    var lthi = instance.snapshots[0];
    var numLayers = lthi.activeTree.renderSurfaceLayerList.length;
    var layer = lthi.activeTree.renderSurfaceLayerList[numLayers - 1];

    var view = new cc.LayerView();
    view.style.height = '500px';
    view.layerTreeImpl = lthi.activeTree;
    view.selection = new cc.LayerSelection(layer);

    this.addHTMLOutput(view);
  });

  test('instantiate_withTileHighlight', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = m.processes[1];

    var instance = p.objects.getAllInstancesNamed('cc::LayerTreeHostImpl')[0];
    var lthi = instance.snapshots[0];
    var numLayers = lthi.activeTree.renderSurfaceLayerList.length;
    var layer = lthi.activeTree.renderSurfaceLayerList[numLayers - 1];
    var tile = lthi.tiles[0];

    var view = new cc.LayerView();
    view.style.height = '500px';
    view.layerTreeImpl = lthi.activeTree;
    view.selection = new cc.TileSelection(tile);
    this.addHTMLOutput(view);
  });
});
