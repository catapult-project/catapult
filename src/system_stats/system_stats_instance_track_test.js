// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.selection');
base.require('tracing.trace_model.event');
base.require('tracing.timeline_viewport');
base.require('tracing.tracks.drawing_container');
base.require('system_stats.system_stats_instance_track');
base.require('system_stats.system_stats_snapshot');

base.unittest.testSuite('system_stats.system_stats_instance_track', function() {
  var SystemStatsInstanceTrack = system_stats.SystemStatsInstanceTrack;
  var Viewport = tracing.TimelineViewport;

  var createObjects = function() {
    var objectInstance = new tracing.trace_model.ObjectInstance({});
    var snapshots = [];

    var stats1 = new Object();
    var stats2 = new Object();

    stats1['committed_memory'] = 2000000;
    stats2['committed_memory'] = 3000000;

    stats1['meminfo'] = new Object();
    stats1.meminfo['free'] = 10000;
    stats2['meminfo'] = new Object();
    stats2.meminfo['free'] = 20000;

    snapshots.push(new system_stats.SystemStatsSnapshot(objectInstance,
                                                        10, stats1));
    snapshots.push(new system_stats.SystemStatsSnapshot(objectInstance,
                                                        20, stats2));

    objectInstance.snapshots = snapshots;

    return objectInstance;
  };

  test('instantiate', function() {
    var objectInstances = [];
    objectInstances.push(createObjects());

    var div = document.createElement('div');
    this.addHTMLOutput(div);

    var viewport = new Viewport(div);
    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
    div.appendChild(drawingContainer);

    var track = SystemStatsInstanceTrack(viewport);
    track.objectInstances = objectInstances;
    drawingContainer.invalidate();
    drawingContainer.appendChild(track);

    track.heading = 'testBasic';
    var dt = new tracing.TimelineDisplayTransform();
    dt.xSetWorldBounds(0, 50, track.clientWidth);
    track.viewport.setDisplayTransformImmediately(dt);
  });
});
