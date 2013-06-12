// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('tracing.timeline_track_view');

'use strict';

base.unittest.testSuite('tracing.tracks.counter_track', function() {
  var Counter = tracing.trace_model.Counter;
  var Viewport = tracing.TimelineViewport;
  var CounterTrack = tracing.tracks.CounterTrack;

  var runTest = function(timestamps, samples, testFn) {
    var testEl = document.createElement('div');
    this.addHTMLOutput(testEl);
    var ctr = new Counter(undefined, 'foo', '', 'foo');
    var n = samples.length / timestamps.length;

    ctr.timestamps = timestamps;
    ctr.samples = samples;
    ctr.seriesNames = [];
    ctr.seriesColors = [];

    for (var i = 0; i < n; ++i) {
      ctr.seriesNames.push('value' + i);
      ctr.seriesColors.push(tracing.getStringColorId(ctr.seriesNames[i]));
    }
    ctr.updateBounds();

    var track = new CounterTrack();
    testEl.appendChild(track);

    var pixelRatio = window.devicePixelRatio || 1;

    track.heading = ctr.name;
    track.counter = ctr;
    track.viewport = new Viewport(testEl);
    track.viewport.xSetWorldBounds(0, 10,
        track.firstCanvas.getBoundingClientRect().width * pixelRatio);

    testFn(ctr, track);
  }

  test('instantiate', function() {
    var ctr = new Counter(undefined, 'testBasicCounter', '',
        'testBasicCounter');
    ctr.seriesNames = ['value1', 'value2'];
    ctr.seriesColors = [tracing.getStringColorId('testBasicCounter.value1'),
                        tracing.getStringColorId('testBasicCounter.value2')];
    ctr.timestamps = [0, 1, 2, 3, 4, 5, 6, 7];
    ctr.samples = [0, 5,
                   3, 3,
                   1, 1,
                   2, 1.1,
                   3, 0,
                   1, 7,
                   3, 0,
                   3.1, 0.5];
    ctr.updateBounds();

    var viewport = document.createElement('div');

    var track = new CounterTrack();
    track.heading = ctr.name;
    track.counter = ctr;
    track.viewport = new Viewport(viewport);
    track.viewport.xSetWorldBounds(0, 7.7, track.clientWidth);
    viewport.appendChild(track);

    this.addHTMLOutput(viewport);
  });

  test('basicCounterXPointPicking', function() {
    var timestamps = [0, 1, 2, 3, 4, 5, 6, 7];
    var samples = [0, 5,
                   3, 3,
                   1, 1,
                   2, 1.1,
                   3, 0,
                   1, 7,
                   3, 0,
                   3.1, 0.5];
    runTest.call(this, timestamps, samples, function(ctr, track) {
      var clientRect = track.firstCanvas.getBoundingClientRect();

      var y75 = clientRect.top + 0.75 * clientRect.height;
      var sel;
      var vW = 10;
      var wW = clientRect.width;

      // In bounds.
      sel = new tracing.Selection();
      var x = (1.5 / vW) * wW;
      track.addIntersectingItemsInRangeToSelection(x, x + 1, y75, y75 + 1, sel);

      assertEquals(1, sel.length);
      assertEquals(track, sel[0].track);
      assertEquals(ctr, sel[0].counter);
      assertEquals(1, sel[0].sampleIndex);

      // Outside bouds.
      sel = new tracing.Selection();
      var x = (-5 / vW) * wW;
      track.addIntersectingItemsInRangeToSelection(x, x + 1, y75, y75 + 1, sel);
      assertEquals(0, sel.length);

      sel = new tracing.Selection();
      var x = (8 / vW) * wW;
      track.addIntersectingItemsInRangeToSelection(x, x + 1, y75, y75 + 1, sel);
      assertEquals(0, sel.length);
    });
  });
});
