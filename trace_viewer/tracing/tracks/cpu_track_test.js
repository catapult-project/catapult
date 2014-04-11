// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.timeline_track_view');
tvcm.require('tracing.trace_model');

tvcm.unittest.testSuite('tracing.tracks.cpu_track_test', function() {
  var Cpu = tracing.trace_model.Cpu;
  var CpuTrack = tracing.tracks.CpuTrack;
  var Slice = tracing.trace_model.Slice;
  var StackFrame = tracing.trace_model.StackFrame;
  var Sample = tracing.trace_model.Sample;
  var Thread = tracing.trace_model.Thread;
  var Viewport = tracing.TimelineViewport;

  test('basicCpu', function() {
    var cpu = new Cpu({}, 7);
    cpu.slices = [
      new Slice('', 'a', 0, 1, {}, 1),
      new Slice('', 'b', 1, 2.1, {}, 4.8)
    ];
    cpu.updateBounds();

    var testEl = document.createElement('div');
    var viewport = new Viewport(testEl);

    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);

    var track = new CpuTrack(viewport);
    drawingContainer.appendChild(track);

    track.heading = 'CPU ' + cpu.cpuNumber;
    track.cpu = cpu;
    var dt = new tracing.TimelineDisplayTransform();
    dt.xSetWorldBounds(0, 11.1, track.clientWidth);
    track.viewport.setDisplayTransformImmediately(dt);
  });


  test('withSamples', function() {
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

    var testEl = document.createElement('div');
    var viewport = new Viewport(testEl);

    var drawingContainer = new tracing.tracks.DrawingContainer(viewport);

    var track = new CpuTrack(viewport);
    drawingContainer.appendChild(track);

    track.heading = 'CPU ' + cpu.cpuNumber;
    track.cpu = cpu;
    var dt = new tracing.TimelineDisplayTransform();
    dt.xSetWorldBounds(0, 11.1, track.clientWidth);
    track.viewport.setDisplayTransformImmediately(dt);
  });
});
