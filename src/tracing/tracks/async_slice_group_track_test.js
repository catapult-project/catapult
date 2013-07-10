// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.timeline_track_view');
base.require('tracing.trace_model');

base.unittest.testSuite('tracing.tracks.async_slice_group_track', function() {
  var AsyncSliceGroup = tracing.trace_model.AsyncSliceGroup;
  var AsyncSliceGroupTrack = tracing.tracks.AsyncSliceGroupTrack;
  var Process = tracing.trace_model.Process;
  var Thread = tracing.trace_model.Thread;
  var newAsyncSlice = tracing.test_utils.newAsyncSlice;

  test('filterSubRows', function() {
    var model = new tracing.TraceModel();
    var p1 = new Process(model, 1);
    var t1 = new Thread(p1, 1);
    var g = new AsyncSliceGroup();
    g.push(newAsyncSlice(0, 1, t1, t1));
    var track = new AsyncSliceGroupTrack(new tracing.TimelineViewport());
    track.group = g;

    assertEquals(1, track.children.length);
    assertTrue(track.hasVisibleContent);

    track.categoryFilter = new tracing.TitleFilter('x');
    assertFalse(track.hasVisibleContent);

    track.categoryFilter = new tracing.TitleFilter('a');
    assertTrue(track.hasVisibleContent);
    assertEquals(1, track.children.length);
  });

  test('rebuildSubRows_twoNonOverlappingSlices', function() {
    var model = new tracing.TraceModel();
    var p1 = new Process(model, 1);
    var t1 = new Thread(p1, 1);
    var g = new AsyncSliceGroup();
    g.push(newAsyncSlice(0, 1, t1, t1));
    g.push(newAsyncSlice(1, 1, t1, t1));
    var track = new AsyncSliceGroupTrack(new tracing.TimelineViewport());
    track.group = g;
    var subRows = track.subRows;
    assertEquals(1, subRows.length);
    assertEquals(2, subRows[0].length);
    assertEquals(g.slices[0].subSlices[0], subRows[0][0]);
    assertEquals(g.slices[1].subSlices[0], subRows[0][1]);
  });

  test('rebuildSubRows_twoOverlappingSlices', function() {
    var model = new tracing.TraceModel();
    var p1 = new Process(model, 1);
    var t1 = new Thread(p1, 1);
    var g = new AsyncSliceGroup();

    g.push(newAsyncSlice(0, 1, t1, t1));
    g.push(newAsyncSlice(0, 1.5, t1, t1));
    g.updateBounds();

    var track = new AsyncSliceGroupTrack(new tracing.TimelineViewport());
    track.group = g;

    var subRows = track.subRows;

    assertEquals(2, subRows.length);
    assertEquals(1, subRows[0].length);
    assertEquals(g.slices[0].subSlices[0], subRows[0][0]);

    assertEquals(1, subRows[1].length);
    assertEquals(g.slices[1].subSlices[0], subRows[1][0]);
  });

  test('rebuildSubRows_threePartlyOverlappingSlices', function() {
    var model = new tracing.TraceModel();
    var p1 = new Process(model, 1);
    var t1 = new Thread(p1, 1);
    var g = new AsyncSliceGroup();
    g.push(newAsyncSlice(0, 1, t1, t1));
    g.push(newAsyncSlice(0, 1.5, t1, t1));
    g.push(newAsyncSlice(1, 1.5, t1, t1));
    g.updateBounds();
    var track = new AsyncSliceGroupTrack(new tracing.TimelineViewport());
    track.group = g;
    var subRows = track.subRows;

    assertEquals(2, subRows.length);
    assertEquals(2, subRows[0].length);
    assertEquals(g.slices[0].subSlices[0], subRows[0][0]);
    assertEquals(g.slices[2].subSlices[0], subRows[0][1]);

    assertEquals(1, subRows[1].length);
    assertEquals(g.slices[1].subSlices[0], subRows[1][0]);
  });

  test('rebuildSubRows_threeOverlappingSlices', function() {
    var model = new tracing.TraceModel();
    var p1 = new Process(model, 1);
    var t1 = new Thread(p1, 1);
    var g = new AsyncSliceGroup();

    g.push(newAsyncSlice(0, 1, t1, t1));
    g.push(newAsyncSlice(0, 1.5, t1, t1));
    g.push(newAsyncSlice(2, 1, t1, t1));
    g.updateBounds();

    var track = new AsyncSliceGroupTrack(new tracing.TimelineViewport());
    track.group = g;

    var subRows = track.subRows;
    assertEquals(2, subRows.length);
    assertEquals(2, subRows[0].length);
    assertEquals(g.slices[0].subSlices[0], subRows[0][0]);
    assertEquals(g.slices[2].subSlices[0], subRows[0][1]);
    assertEquals(1, subRows[1].length);
    assertEquals(g.slices[1].subSlices[0], subRows[1][0]);
  });

  test('computeSubGroups_twoThreadSpecificSlices', function() {
    var model = new tracing.TraceModel();
    var p1 = new Process(model, 1);
    var t1 = new Thread(p1, 1);
    var t2 = new Thread(p1, 2);
    var g = new AsyncSliceGroup();
    g.push(newAsyncSlice(0, 1, t1, t1));
    g.push(newAsyncSlice(0, 1, t2, t2));
    var track = new AsyncSliceGroupTrack(new tracing.TimelineViewport());
    track.group = g;
    var subRows = track.subRows;

    var subGroups = g.computeSubGroups();
    assertEquals(2, subGroups.length);

    assertEquals(g.name, subGroups[0].name);
    assertEquals(1, subGroups[0].slices.length);
    assertEquals(g.slices[0], subGroups[0].slices[0]);

    assertEquals(g.name, subGroups[1].name);
    assertEquals(1, subGroups[1].slices.length);
    assertEquals(g.slices[1], subGroups[1].slices[0]);
  });
});
