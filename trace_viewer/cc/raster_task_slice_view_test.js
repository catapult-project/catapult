// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('cc.raster_task_slice_view');
tvcm.require('tracing.importer.trace_event_importer');
tvcm.require('tracing.trace_model');
tvcm.requireRawScript('cc/layer_tree_host_impl_test_data.js');

tvcm.unittest.testSuite('cc.raster_task_slice_view_test', function() {
  test('instantiate', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = m.processes[1];

    var rasterTask = p.threads[1].sliceGroup.slices.filter(function(slice) {
      return slice.title == 'TileManager::RunRasterTask';
    })[0];

    var view = new cc.RasterTaskSliceView();
    view.style.minHeight = '500px';
    view.slice = rasterTask;
    this.addHTMLOutput(view);
  });
});
