// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.timeline_track_view');

base.unittest.testSuite('tracing.tracks.counter_track', function() {
  var Counter = tracing.trace_model.Counter;
  var Viewport = tracing.TimelineViewport;
  var CounterTrack = tracing.tracks.CounterTrack;

  var runTest = function(timestamps, samples, testFn) {
    var testEl = document.createElement('div');
    this.addHTMLOutput(testEl);

    var ctr = new Counter(undefined, 'foo', '', 'foo');
    var n = samples.length;

    for (var i = 0; i < n; ++i) {
      ctr.addSeries(new tracing.trace_model.CounterSeries('value' + i,
          tracing.getStringColorId('value' + i)));
    }

    for (var i = 0; i < samples.length; ++i) {
      for (var k = 0; k < timestamps.length; ++k) {
        ctr.series[i].addSample(timestamps[k], samples[i][k]);
      }
    }

    ctr.updateBounds();

    var viewport = new Viewport(testEl);

    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
    testEl.appendChild(drawingContainer);

    var track = new CounterTrack(viewport);
    drawingContainer.appendChild(track);

    // Force the container to update sizes so the test can use coordinates that
    // make sense. This has to be after the adding of the track as we need to
    // use the track header to figure out our positioning.
    drawingContainer.updateCanvasSizeIfNeeded_();

    var pixelRatio = window.devicePixelRatio || 1;

    track.heading = ctr.name;
    track.counter = ctr;
    track.viewport.xSetWorldBounds(0, 10, track.clientWidth * pixelRatio);

    testFn(ctr, drawingContainer, track);
  };

  test('instantiate', function() {
    var ctr = new Counter(undefined, 'testBasicCounter', '',
        'testBasicCounter');
    ctr.addSeries(new tracing.trace_model.CounterSeries('value1',
        tracing.getStringColorId('testBasicCounter.value1')));
    ctr.addSeries(new tracing.trace_model.CounterSeries('value2',
        tracing.getStringColorId('testBasicCounter.value2')));

    var timestamps = [0, 1, 2, 3, 4, 5, 6, 7];
    var samples = [[0, 3, 1, 2, 3, 1, 3, 3.1],
                   [5, 3, 1, 1.1, 0, 7, 0, 0.5]];
    for (var i = 0; i < samples.length; ++i) {
      for (var k = 0; k < timestamps.length; ++k) {
        ctr.series[i].addSample(timestamps[k], samples[i][k]);
      }
    }

    ctr.updateBounds();

    var div = document.createElement('div');
    this.addHTMLOutput(div);

    var viewport = new Viewport(div);

    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
    div.appendChild(drawingContainer);
    drawingContainer.invalidate();

    var track = new CounterTrack(viewport);
    drawingContainer.appendChild(track);

    track.heading = ctr.name;
    track.counter = ctr;
    track.viewport.xSetWorldBounds(0, 7.7, track.clientWidth);
  });

  test('basicCounterXPointPicking', function() {
    var timestamps = [0, 1, 2, 3, 4, 5, 6, 7];
    var samples = [[0, 3, 1, 2, 3, 1, 3, 3.1],
                   [5, 3, 1, 1.1, 0, 7, 0, 0.5]];

    runTest.call(this, timestamps, samples, function(ctr, container, track) {
      var clientRect = track.getBoundingClientRect();
      var y75 = clientRect.top + (0.75 * clientRect.height);

      // In bounds.
      var sel = new tracing.Selection();
      var x = 0.15 * clientRect.width;
      track.addIntersectingItemsInRangeToSelection(x, x + 1, y75, y75 + 1, sel);

      assertEquals(1, sel.length);
      assertEquals(track, sel[0].track);
      assertEquals(ctr, sel[0].counter);
      assertEquals(1, sel[0].sampleIndex);

      // Outside bounds.
      sel = new tracing.Selection();
      var x = -0.5 * clientRect.width;
      track.addIntersectingItemsInRangeToSelection(x, x + 1, y75, y75 + 1, sel);
      assertEquals(0, sel.length);

      sel = new tracing.Selection();
      var x = 0.8 * clientRect.width;
      track.addIntersectingItemsInRangeToSelection(x, x + 1, y75, y75 + 1, sel);
      assertEquals(0, sel.length);
    });
  });
});
