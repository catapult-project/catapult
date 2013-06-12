base.require('cc');
base.require('tracing.importer.trace_event_importer');
base.require('tracing.trace_model');

'use strict';

base.unittest.testSuite('cc.layer_viewer', function() {
  test('instantiate', function() {
    var m = new tracing.TraceModel(g_catLTHIEvents);
    var p = m.processes[1];

    var instance = p.objects.getAllInstancesNamed('cc::LayerTreeHostImpl')[0];
    var snapshot = instance.snapshots[0];
    var layer = snapshot.activeTree.renderSurfaceLayerList[0];

    var viewer = new cc.LayerViewer();
    viewer.style.height = '500px';
    viewer.layer = layer;
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
    viewer.layer = layer;

    viewer.highlight = {
      quadIfActive: tile.args.activePriority.currentScreenQuad,
      quadIfPending: tile.args.pendingPriority.currentScreenQuad,
      objectToAnalyze: tile
    };
    this.addHTMLOutput(viewer);
  });
});
