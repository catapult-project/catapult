// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('tracing.timeline_track_view');
base.require('tracing.tracks.thread_track');

'use strict';

base.unittest.testSuite('tracing.tracks.thread_track', function() {
  var Process = tracing.trace_model.Process;
  var Selection = tracing.Selection;
  var Thread = tracing.trace_model.Thread;
  var ThreadSlice = tracing.trace_model.ThreadSlice;
  var ThreadTrack = tracing.tracks.ThreadTrack;
  var Viewport = tracing.TimelineViewport;
  var newAsyncSlice = tracing.test_utils.newAsyncSlice;
  var newAsyncSliceNamed = tracing.test_utils.newAsyncSliceNamed;
  var newSliceNamed = tracing.test_utils.newSliceNamed;

  test('selectionHitTestingWithThreadTrack', function() {
    var model = new tracing.TraceModel();
    var p1 = model.getOrCreateProcess(1);
    var t1 = p1.getOrCreateThread(1);
    t1.pushSlice(new ThreadSlice('', 'a', 0, 1, {}, 4));
    t1.pushSlice(new ThreadSlice('', 'b', 0, 5.1, {}, 4));

    var testEl = document.createElement('div');
    testEl.style.width = '600px';

    var track = new ThreadTrack();
    testEl.appendChild(track);
    track.heading = 'testSelectionHitTestingWithThreadTrack';
    track.headingWidth = '100px';
    track.thread = t1;

    var y = track.getBoundingClientRect().top;
    var h = track.getBoundingClientRect().height;
    var wW = 10;
    var vW = track.firstCanvas.getBoundingClientRect().width;
    track.viewport = new Viewport(testEl);
    track.viewport.xSetWorldBounds(0, wW, vW);

    var selection = new Selection();
    var x = (1.5 / wW) * vW;
    track.addIntersectingItemsInRangeToSelection(x, x + 1, y, y + 1, selection);
    assertEquals(t1.slices[0], selection[0].slice);

    var selection = new Selection();
    track.addIntersectingItemsInRangeToSelection(
        (1.5 / wW) * vW, (1.8 / wW) * vW,
        y, y + h, selection);
    assertEquals(t1.slices[0], selection[0].slice);
  });

  test('filterThreadSlices', function() {
    var thread = new Thread(new Process(7), 1);
    thread.pushSlice(newSliceNamed('a', 0, 0));
    thread.asyncSlices.push(newAsyncSliceNamed('a', 0, 5, t, t));

    var t = new ThreadTrack();
    t.thread = thread;

    assertTrue(t.tracks_[1].visible);
    assertEquals(1, t.tracks_[1].tracks_.length);
    assertTrue(t.tracks_[1].visible);
    assertEquals(1, t.tracks_[2].tracks_.length);

    t.categoryFilter = new tracing.TitleFilter('x');
    assertFalse(t.tracks_[1].visible);
    assertFalse(t.tracks_[1].visible);

    t.categoryFilter = new tracing.TitleFilter('a');
    assertTrue(t.tracks_[1].visible);
    assertEquals(1, t.tracks_[1].tracks_.length);
    assertTrue(t.tracks_[1].visible);
    assertEquals(1, t.tracks_[2].tracks_.length);
  });

  test('sampleThreadSlices', function() {
    var thread = new Thread(new Process(7), 1);
    thread.addSample('a', 'b', 0);
    thread.addSample('a', 'c', 5);
    thread.addSample('aa', 'd', 10);
    thread.addSample('aa', 'e', 15);
    var t = new ThreadTrack();
    t.thread = thread;
    // Track is visible.
    assertTrue(t.tracks_[3].visible);
    // Track has 4 slices.
    assertEquals(t.tracks_[3].slices.length, 4);
  });
});
