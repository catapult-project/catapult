// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.trace_model');

tvcm.unittest.testSuite('tracing.trace_model.cpu_test', function() {
  var Cpu = tracing.trace_model.Cpu;

  test('cpuBounds_Empty', function() {
    var cpu = new Cpu({}, 1);
    cpu.updateBounds();
    assertEquals(undefined, cpu.bounds.min);
    assertEquals(undefined, cpu.bounds.max);
  });

  test('cpuBounds_OneSlice', function() {
    var cpu = new Cpu({}, 1);
    cpu.slices.push(tracing.test_utils.newSlice(1, 3));
    cpu.updateBounds();
    assertEquals(1, cpu.bounds.min);
    assertEquals(4, cpu.bounds.max);
  });

  test('getOrCreateCounter', function() {
    var cpu = new Cpu({}, 1);
    var ctrBar = cpu.getOrCreateCounter('foo', 'bar');
    var ctrBar2 = cpu.getOrCreateCounter('foo', 'bar');
    assertEquals(ctrBar2, ctrBar);
  });

  test('shiftTimestampsForward', function() {
    var cpu = new Cpu({}, 1);
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


  function newCpuSliceNamed(cpu, name, start, duration, opt_thread) {
    var s = new tracing.trace_model.CpuSlice(
        'cat', name, 0, start, {}, duration);
    s.cpu = cpu;
    if (opt_thread)
      s.threadThatWasRunning = opt_thread;
    return s;
  }

  function newTimeSliceNamed(thread, name, start, duration, opt_cpu) {
    var s = new tracing.trace_model.ThreadTimeSlice(
        thread, 'cat', name, 0, start, {}, duration);
    if (opt_cpu)
      s.cpuOnWhichThreadWasRunning = opt_cpu;
    return s;
  }

  test('getTimesliceForCpuSlice', function() {
    var m = new tracing.TraceModel();
    var cpu = m.kernel.getOrCreateCpu(1);
    var t2 = m.getOrCreateProcess(1).getOrCreateThread(2);
    t2.timeSlices = [newTimeSliceNamed(t2, 'Running', 0, 10, cpu),
                     newTimeSliceNamed(t2, 'Sleeping', 10, 10),
                     newTimeSliceNamed(t2, 'Running', 20, 10, cpu)];
    cpu.slices = [newCpuSliceNamed(cpu, 'x', 0, 10, t2),
                  newCpuSliceNamed(cpu, 'x', 20, 10, t2)];
    assertEquals(t2.timeSlices[0], cpu.slices[0].getAssociatedTimeslice());
    assertEquals(t2.timeSlices[2], cpu.slices[1].getAssociatedTimeslice());

    assertEquals(cpu.slices[0], t2.timeSlices[0].getAssociatedCpuSlice());
    assertEquals(undefined, t2.timeSlices[1].getAssociatedCpuSlice());
    assertEquals(cpu.slices[1], t2.timeSlices[2].getAssociatedCpuSlice());

    assertEquals(0, cpu.indexOf(cpu.slices[0]));
    assertEquals(1, cpu.indexOf(cpu.slices[1]));

    assertEquals(0, t2.indexOfTimeSlice(t2.timeSlices[0]));
    assertEquals(1, t2.indexOfTimeSlice(t2.timeSlices[1]));
    assertEquals(2, t2.indexOfTimeSlice(t2.timeSlices[2]));
  });

  test('putToSleepFor', function() {
    var m = new tracing.TraceModel();
    var cpu = m.kernel.getOrCreateCpu(1);

    var t2 = m.getOrCreateProcess(1).getOrCreateThread(2);
    var t3 = m.getOrCreateProcess(1).getOrCreateThread(3);
    t2.timeSlices = [newTimeSliceNamed(t2, 'Running', 0, 10, cpu),
                     newTimeSliceNamed(t2, 'Sleeping', 10, 10),
                     newTimeSliceNamed(t2, 'Running', 20, 10, cpu)];
    t3.timeSlices = [newTimeSliceNamed(t3, 'Running', 10, 5, cpu)];
    cpu.slices = [newCpuSliceNamed(cpu, 'x', 0, 10, t2),
                   newCpuSliceNamed(cpu, 'x', 10, 5, t3),
                   newCpuSliceNamed(cpu, 'x', 20, 10, t2)];

    // At timeslice 0, the thread is running.
    assertEquals(
        undefined, t2.timeSlices[0].getCpuSliceThatTookCpu());

    // t2 lost the cpu to t3 at t=10
    assertEquals(
        cpu.slices[1],
        t2.timeSlices[1].getCpuSliceThatTookCpu());
  });

  test('putToSleepForNothing', function() {
    var m = new tracing.TraceModel();
    var cpu = m.kernel.getOrCreateCpu(1);

    var t2 = m.getOrCreateProcess(1).getOrCreateThread(2);
    var t3 = m.getOrCreateProcess(1).getOrCreateThread(3);
    t2.timeSlices = [newTimeSliceNamed(t2, 'Running', 0, 10, cpu),
                     newTimeSliceNamed(t2, 'Sleeping', 10, 10),
                     newTimeSliceNamed(t2, 'Running', 20, 10, cpu)];
    t3.timeSlices = [newTimeSliceNamed(t3, 'Running', 15, 5, cpu)];
    cpu.slices = [newCpuSliceNamed(cpu, 'x', 0, 10, t2),
                   newCpuSliceNamed(cpu, 'x', 15, 5, t3),
                   newCpuSliceNamed(cpu, 'x', 20, 10, t2)];
    assertEquals(
        undefined,
        t2.timeSlices[1].getCpuSliceThatTookCpu());
  });
});
