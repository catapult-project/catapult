// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.trace_model');

base.unittest.testSuite('tracing.trace_model.thread', function() {
  var ThreadSlice = tracing.trace_model.ThreadSlice;
  var Process = tracing.trace_model.Process;
  var Thread = tracing.trace_model.Thread;
  var newSliceNamed = tracing.test_utils.newSliceNamed;
  var newAsyncSlice = tracing.test_utils.newAsyncSlice;

  test('threadBounds_Empty', function() {
    var model = new tracing.TraceModel();
    var t = new Thread(new Process(model, 7), 1);
    t.updateBounds();
    assertEquals(undefined, t.bounds.min);
    assertEquals(undefined, t.bounds.max);
  });

  test('threadBounds_SubRow', function() {
    var model = new tracing.TraceModel();
    var t = new Thread(new Process(model, 7), 1);
    t.sliceGroup.pushSlice(new ThreadSlice('', 'a', 0, 1, {}, 3));
    t.updateBounds();
    assertEquals(1, t.bounds.min);
    assertEquals(4, t.bounds.max);
  });

  test('threadBounds_AsyncSliceGroup', function() {
    var model = new tracing.TraceModel();
    var t = new Thread(new Process(model, 7), 1);
    t.sliceGroup.pushSlice(new ThreadSlice('', 'a', 0, 1, {}, 3));
    t.asyncSliceGroup.push(newAsyncSlice(0.1, 5, t, t));
    t.updateBounds();
    assertEquals(0.1, t.bounds.min);
    assertEquals(5.1, t.bounds.max);
  });

  test('threadBounds_Cpu', function() {
    var model = new tracing.TraceModel();
    var t = new Thread(new Process(model, 7), 1);
    t.cpuSlices = [newSliceNamed('x', 0, 1)];
    t.updateBounds();
    assertEquals(0, t.bounds.min);
    assertEquals(1, t.bounds.max);
  });

  test('shiftTimestampsForwardWithCpu', function() {
    var model = new tracing.TraceModel();
    var t = new Thread(new Process(model, 7), 1);
    t.sliceGroup.pushSlice(new ThreadSlice('', 'a', 0, 0, {}, 3));
    t.asyncSliceGroup.push(newAsyncSlice(0, 5, t, t));
    t.cpuSlices = [newSliceNamed('x', 0, 1)];

    var shiftCount = 0;
    t.asyncSliceGroup.shiftTimestampsForward = function(ts) {
      if (ts == 0.32)
        shiftCount++;
    };

    t.shiftTimestampsForward(0.32);

    assertEquals(1, shiftCount);
    assertEquals(0.32, t.sliceGroup.slices[0].start);
    assertEquals(0.32, t.cpuSlices[0].start);
  });

  test('shiftTimestampsForwardWithoutCpu', function() {
    var model = new tracing.TraceModel();
    var t = new Thread(new Process(model, 7), 1);
    t.sliceGroup.pushSlice(new ThreadSlice('', 'a', 0, 0, {}, 3));
    t.asyncSliceGroup.push(newAsyncSlice(0, 5, t, t));

    var shiftCount = 0;
    t.asyncSliceGroup.shiftTimestampsForward = function(ts) {
      if (ts == 0.32)
        shiftCount++;
    };

    t.shiftTimestampsForward(0.32);

    assertEquals(1, shiftCount);
    assertEquals(0.32, t.sliceGroup.slices[0].start);
  });
});
