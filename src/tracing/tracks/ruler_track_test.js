// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.timeline_viewport');
base.require('tracing.tracks.drawing_container');
base.require('tracing.tracks.ruler_track');

base.unittest.testSuite('tracing.tracks.ruler_track', function() {
  test('instantiate', function() {
    var div = document.createElement('div');
    this.addHTMLOutput(div);

    var viewport = new tracing.TimelineViewport(div);
    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);
    div.appendChild(drawingContainer);

    var track = tracing.tracks.RulerTrack(viewport);
    drawingContainer.appendChild(track);
    drawingContainer.invalidate();

    track.viewport.setPanAndScale(0, track.clientWidth / 1000);
  });
});
