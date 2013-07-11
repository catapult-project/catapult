// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.timeline_track_view');
base.require('tracing.tracks.thread_track');
base.require('ui.dom_helpers');

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
    t1.sliceGroup.pushSlice(new ThreadSlice('', 'a', 0, 1, {}, 4));
    t1.sliceGroup.pushSlice(new ThreadSlice('', 'b', 0, 5.1, {}, 4));

    var testEl = document.createElement('div');
    testEl.appendChild(ui.createScopedStyle('heading { width: 100px; }'));
    testEl.style.width = '600px';

    var viewport = new Viewport(testEl);
    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
    testEl.appendChild(drawingContainer);

    var track = new ThreadTrack(viewport);
    drawingContainer.appendChild(track);
    drawingContainer.updateCanvasSizeIfNeeded_();
    track.thread = t1;

    var y = track.getBoundingClientRect().top;
    var h = track.getBoundingClientRect().height;
    var wW = 10;
    var vW = drawingContainer.canvas.getBoundingClientRect().width;
    track.viewport.xSetWorldBounds(0, wW, vW);

    var selection = new Selection();
    var x = (1.5 / wW) * vW;
    track.addIntersectingItemsInRangeToSelection(x, x + 1, y, y + 1, selection);
    assertEquals(t1.sliceGroup.slices[0], selection[0].slice);

    var selection = new Selection();
    track.addIntersectingItemsInRangeToSelection(
        (1.5 / wW) * vW, (1.8 / wW) * vW,
        y, y + h, selection);
    assertEquals(t1.sliceGroup.slices[0], selection[0].slice);
  });

  test('filterThreadSlices', function() {
    var model = new tracing.TraceModel();
    var thread = new Thread(new Process(model, 7), 1);
    thread.sliceGroup.pushSlice(newSliceNamed('a', 0, 0));
    thread.asyncSliceGroup.push(newAsyncSliceNamed('a', 0, 5, t, t));

    var t = new ThreadTrack(new tracing.TimelineViewport());
    t.thread = thread;

    assertEquals(t.tracks_.length, 2);
    assertTrue(t.tracks_[0] instanceof tracing.tracks.AsyncSliceGroupTrack);
    assertTrue(t.tracks_[1] instanceof tracing.tracks.SliceGroupTrack);

    t.categoryFilter = new tracing.TitleFilter('x');
    assertEquals(0, t.tracks_.length);

    t.categoryFilter = new tracing.TitleFilter('a');
    assertTrue(t.tracks_[0] instanceof tracing.tracks.AsyncSliceGroupTrack);
    assertTrue(t.tracks_[1] instanceof tracing.tracks.SliceGroupTrack);
  });

  test('sampleThreadSlices', function() {
    var model = new tracing.TraceModel();
    var thread = new Thread(new Process(model, 7), 1);
    thread.addSample('a', 'b', 0);
    thread.addSample('a', 'c', 5);
    thread.addSample('aa', 'd', 10);
    thread.addSample('aa', 'e', 15);
    var t = new ThreadTrack(new tracing.TimelineViewport());
    t.thread = thread;
    assertEquals(1, t.tracks_.length);
    assertTrue(t.tracks_[0] instanceof tracing.tracks.SliceTrack);
    assertTrue(4, t.tracks_[0].slices.length);
  });
});
