// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.timeline_track_view');
tvcm.require('tracing.tracks.thread_track');
tvcm.require('tvcm.ui.dom_helpers');

tvcm.unittest.testSuite('tracing.tracks.thread_track_test', function() {
  var Process = tracing.trace_model.Process;
  var Selection = tracing.Selection;
  var StackFrame = tracing.trace_model.StackFrame;
  var Sample = tracing.trace_model.Sample;
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
    testEl.appendChild(tvcm.ui.createScopedStyle('heading { width: 100px; }'));
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
    var dt = new tracing.TimelineDisplayTransform();
    dt.xSetWorldBounds(0, wW, vW);
    track.viewport.setDisplayTransformImmediately(dt);

    var selection = new Selection();
    var x = (1.5 / wW) * vW;
    track.addIntersectingItemsInRangeToSelection(x, x + 1, y, y + 1, selection);
    assertEquals(t1.sliceGroup.slices[0], selection[0]);

    var selection = new Selection();
    track.addIntersectingItemsInRangeToSelection(
        (1.5 / wW) * vW, (1.8 / wW) * vW,
        y, y + h, selection);
    assertEquals(t1.sliceGroup.slices[0], selection[0]);
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
  });

  test('sampleThreadSlices', function() {
    var model = new tracing.TraceModel();
    var thread;
    var cpu;
    model.importTraces([], false, false, function() {
      cpu = model.kernel.getOrCreateCpu(1);
      thread = model.getOrCreateProcess(1).getOrCreateThread(2);

      var fA = model.addStackFrame(new StackFrame(
          undefined, 1, 'cat', 'a', 7));
      var fAB = model.addStackFrame(new StackFrame(
          fA, 2, 'cat', 'b', 7));
      var fABC = model.addStackFrame(new StackFrame(
          fAB, 3, 'cat', 'c', 7));
      var fAD = model.addStackFrame(new StackFrame(
          fA, 4, 'cat', 'd', 7));

      model.samples.push(new Sample(undefined, thread, 'instructions_retired',
                                    10, fABC, 10));
      model.samples.push(new Sample(undefined, thread, 'instructions_retired',
                                    20, fAB, 10));
      model.samples.push(new Sample(undefined, thread, 'instructions_retired',
                                    30, fAB, 10));
      model.samples.push(new Sample(undefined, thread, 'instructions_retired',
                                    40, fAD, 10));

      model.samples.push(new Sample(undefined, thread, 'page_fault',
                                    25, fAB, 10));
      model.samples.push(new Sample(undefined, thread, 'page_fault',
                                    35, fAD, 10));
    });

    var t = new ThreadTrack(new tracing.TimelineViewport());
    t.thread = thread;
    assertEquals(2, t.tracks_.length);

    // Instructions retired
    var t0 = t.tracks_[0];
    assertTrue(t0.heading.indexOf('instructions_retired') != -1);
    assertTrue(t0 instanceof tracing.tracks.SliceTrack);
    assertTrue(4, t0.slices.length);
    t0.slices.forEach(function(s) {
      assertTrue(s instanceof tracing.trace_model.Sample);
    });

    // page_fault
    var t1 = t.tracks_[1];
    assertTrue(t1.heading.indexOf('page_fault') != -1);
    assertTrue(t1 instanceof tracing.tracks.SliceTrack);
    assertTrue(2, t1.slices.length);
  });
});
