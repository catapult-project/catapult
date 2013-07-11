// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.timeline_track_view');
base.require('tracing.trace_model');

base.unittest.testSuite('tracing.tracks.cpu_track', function() {
  var Cpu = tracing.trace_model.Cpu;
  var CpuTrack = tracing.tracks.CpuTrack;
  var Slice = tracing.trace_model.Slice;
  var Viewport = tracing.TimelineViewport;

  test('basicCpu', function() {
    var testEl = document.createElement('div');

    var cpu = new Cpu(7);
    cpu.slices = [
      new Slice('', 'a', 0, 1, {}, 1),
      new Slice('', 'b', 1, 2.1, {}, 4.8)
    ];
    cpu.updateBounds();

    var viewport = new Viewport(testEl);

    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);

    var track = CpuTrack(viewport);
    drawingContainer.appendChild(track);

    track.heading = 'CPU ' + cpu.cpuNumber;
    track.cpu = cpu;
    track.viewport.xSetWorldBounds(0, 11.1, track.clientWidth);
  });
});
