// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('tracing.selection');
base.require('tracing.trace_model.object_collection');
base.require('tracing.timeline_viewport');
base.require('tracing.tracks.object_instance_track');

'use strict';

base.unittest.testSuite('tracing.tracks.object_instance_track', function() {
  var Selection = tracing.Selection;
  var ObjectInstanceTrack = tracing.tracks.ObjectInstanceTrack;
  var Viewport = tracing.TimelineViewport;

  var createObjects = function() {
    var objects = new tracing.trace_model.ObjectCollection({});
    objects.idWasCreated('0x1000', 'cc', 'Frame', 10);
    objects.addSnapshot('0x1000', 'cc', 'Frame', 10, 'snapshot-1');
    objects.addSnapshot('0x1000', 'cc', 'Frame', 25, 'snapshot-2');
    objects.addSnapshot('0x1000', 'cc', 'Frame', 40, 'snapshot-3');
    objects.idWasDeleted('0x1000', 'cc', 'Frame', 45);

    objects.idWasCreated('0x1001', 'skia', 'Picture', 20);
    objects.addSnapshot('0x1001', 'skia', 'Picture', 20, 'snapshot-1');
    objects.idWasDeleted('0x1001', 'skia', 'Picture', 25);
    return objects;
  };

  function testBasic() {
    var objects = createObjects();
    var frames = objects.getAllInstancesByTypeName()['Frame'];
    frames[0].snapshots[1].selected = true;

    var viewport = document.createElement('div');
    var track = ObjectInstanceTrack();
    track.heading = 'testBasic';
    track.objectInstances = frames;
    track.viewport = new Viewport(viewport);
    track.viewport.xSetWorldBounds(0, 50, track.clientWidth);
    viewport.appendChild(trace);

    this.addHTMLOutput(viewport);
  }

  test('selectionHitTestingWithThreadTrack', function() {
    var objects = createObjects();
    var frames = objects.getAllInstancesByTypeName()['Frame'];

    var track = ObjectInstanceTrack();
    track.objectInstances = frames;

    // Hit outside range
    var selection = new Selection();
    track.addIntersectingItemsInRangeToSelectionInWorldSpace(
        8, 8.1, 0.1, selection);
    assertEquals(0, selection.length);

    // Hit the first snapshot, via pixel-nearness.
    selection = new Selection();
    track.addIntersectingItemsInRangeToSelectionInWorldSpace(
        9.98, 9.99, 0.1, selection);
    assertEquals(1, selection.length);
    assertEquals(1, selection.getNumObjectSnapshotHits());

    // Hit the instance, between the 1st and 2nd snapshots
    selection = new Selection();
    track.addIntersectingItemsInRangeToSelectionInWorldSpace(
        20, 20.1, 0.1, selection);
    assertEquals(1, selection.length);
    assertEquals(1, selection.getNumObjectInstanceHits());
  });
});
