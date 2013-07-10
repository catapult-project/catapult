// Copyright (c) 2012 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.timeline_viewport');
base.require('tracing.tracks.ruler_track');

base.unittest.testSuite('tracing.tracks.ruler_track', function() {
  test('instantiate', function() {
    var viewport = document.createElement('div');
    this.addHTMLOutput(viewport);

    var track = tracing.tracks.RulerTrack(
        new tracing.TimelineViewport(viewport));
    viewport.appendChild(track);

    track.viewport.setPanAndScale(0, track.clientWidth / 1000);
  });
});
