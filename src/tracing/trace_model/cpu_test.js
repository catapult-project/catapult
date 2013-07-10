// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.trace_model.cpu');

base.unittest.testSuite('tracing.trace_model.cpu', function() {
  var Cpu = tracing.trace_model.Cpu;

  test('cpuBounds_Empty', function() {
    var cpu = new Cpu(undefined, 1);
    cpu.updateBounds();
    assertEquals(undefined, cpu.bounds.min);
    assertEquals(undefined, cpu.bounds.max);
  });

  test('cpuBounds_OneSlice', function() {
    var cpu = new Cpu(undefined, 1);
    cpu.slices.push(tracing.test_utils.newSlice(1, 3));
    cpu.updateBounds();
    assertEquals(1, cpu.bounds.min);
    assertEquals(4, cpu.bounds.max);
  });

  test('getOrCreateCounter', function() {
    var cpu = new Cpu(undefined, 1);
    var ctrBar = cpu.getOrCreateCounter('foo', 'bar');
    var ctrBar2 = cpu.getOrCreateCounter('foo', 'bar');
    assertEquals(ctrBar2, ctrBar);
  });

  test('shiftTimestampsForward', function() {
    var cpu = new Cpu(undefined, 1);
    var ctr = cpu.getOrCreateCounter('foo', 'bar');
    cpu.slices.push(tracing.test_utils.newSlice(1, 3));
    var shiftCount = 0;
    ctr.shiftTimestampsForward = function(ts) {
      if (ts == 0.32)
        shiftCount++;
    };
    cpu.slices.push(tracing.test_utils.newSlice(1, 3));
    cpu.shiftTimestampsForward(0.32);
    assertEquals(shiftCount, 1);
    assertEquals(1.32, cpu.slices[0].start);
  });
});
