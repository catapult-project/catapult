base.require('cc.raster_task_slice_view');
base.require('tracing.importer.trace_event_importer');
base.require('tracing.trace_model');

'use strict';

base.unittest.testSuite('cc.raster_task_slice_view', function() {
  test('instantiate', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = m.processes[1];

    var rasterTask = p.threads[1].slices.filter(function(slice) {
      return slice.title == 'TileManager::RunRasterTask';
    })[0];

    var view = new cc.RasterTaskSliceView();
    view.style.minHeight = '500px';
    view.slice = rasterTask;
    this.addHTMLOutput(view);
  });
});
