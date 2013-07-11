// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.timeline_viewport');
base.require('tracing.test_utils');
base.require('tracing.trace_model');
base.require('tracing.selection');
base.require('tracing.tracks.slice_track');

base.unittest.testSuite('tracing.selection', function() {
  test('selectionObject', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var t1 = p1.getOrCreateThread(1);
    t1.sliceGroup.pushSlice(
        new tracing.trace_model.ThreadSlice('', 'a', 0, 1, {}, 3));
    t1.sliceGroup.pushSlice(
        new tracing.trace_model.ThreadSlice('', 'a', 0, 5, {}, 1));

    var sel = new tracing.Selection();
    sel.addSlice({}, t1.sliceGroup.slices[0]);

    assertEquals(1, sel.bounds.min);
    assertEquals(4, sel.bounds.max);
    assertEquals(t1.sliceGroup.slices[0], sel[0].slice);

    sel.addSlice({}, t1.sliceGroup.slices[1]);
    assertEquals(1, sel.bounds.min);
    assertEquals(6, sel.bounds.max);
    assertEquals(t1.sliceGroup.slices[1], sel[1].slice);

    sel.clear();
    assertEquals(0, sel.length);
  });

  test('shiftedSelection', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var t1 = p1.getOrCreateThread(1);
    t1.sliceGroup.pushSlice(
        new tracing.trace_model.ThreadSlice('', 'a', 0, 1, {}, 3));
    t1.sliceGroup.pushSlice(
        new tracing.trace_model.ThreadSlice('', 'a', 0, 5, {}, 1));

    var track = new tracing.tracks.SliceTrack(new tracing.TimelineViewport());
    track.slices = t1.sliceGroup.slices;

    var sel = new tracing.Selection();
    sel.addSlice(track, t1.sliceGroup.slices[0]);

    var shifted = sel.getShiftedSelection(1);
    assertEquals(1, shifted.length);
    assertEquals(t1.sliceGroup.slices[1], shifted[0].slice);
  });
});
