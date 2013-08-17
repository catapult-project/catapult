// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.analysis.cpu_slice_view');
base.require('tracing.trace_model');
base.require('tracing.timeline_view');
base.require('tracing.importer.linux_perf_importer');


base.unittest.testSuite('tracing.analysis.thread_time_slice_view', function() {
  function createBasicModel() {
    var lines = [
      'Android.launcher-584   [001] d..3 12622.506890: sched_switch: prev_comm=Android.launcher prev_pid=584 prev_prio=120 prev_state=R+ ==> next_comm=Binder_1 next_pid=217 next_prio=120', // @suppress longLineCheck
      '       Binder_1-217   [001] d..3 12622.506918: sched_switch: prev_comm=Binder_1 prev_pid=217 prev_prio=120 prev_state=D ==> next_comm=Android.launcher next_pid=584 next_prio=120', // @suppress longLineCheck
      'Android.launcher-584   [001] d..4 12622.506936: sched_wakeup: comm=Binder_1 pid=217 prio=120 success=1 target_cpu=001', // @suppress longLineCheck
      'Android.launcher-584   [001] d..3 12622.506950: sched_switch: prev_comm=Android.launcher prev_pid=584 prev_prio=120 prev_state=R+ ==> next_comm=Binder_1 next_pid=217 next_prio=120', // @suppress longLineCheck
      '       Binder_1-217   [001] ...1 12622.507057: tracing_mark_write: B|128|queueBuffer', // @suppress longLineCheck
      '       Binder_1-217   [001] ...1 12622.507175: tracing_mark_write: E',
      '       Binder_1-217   [001] d..3 12622.507253: sched_switch: prev_comm=Binder_1 prev_pid=217 prev_prio=120 prev_state=S ==> next_comm=Android.launcher next_pid=584 next_prio=120' // @suppress longLineCheck
    ];

    return new tracing.TraceModel(lines.join('\n'), false);
  }

  test('runningSlice', function() {
    var m = createBasicModel();

    var cpu = m.kernel.cpus[1];
    var binderSlice = cpu.slices[0];
    assertEquals('Binder_1', binderSlice.title);
    var launcherSlice = cpu.slices[1];
    assertEquals('Android.launcher', launcherSlice.title);


    var thread = m.findAllThreadsNamed('Binder_1')[0];

    var view = new tracing.analysis.ThreadTimeSliceView();
    view.modelEvent = thread.timeSlices[0];
    this.addHTMLOutput(view);

    // Clicking the analysis link should focus the Binder1's timeslice.
    var didSelectionChangeHappen = false;
    view.addEventListener('requestSelectionChange', function(e) {
      assertEquals(1, e.selection.length);
      assertEquals(binderSlice, e.selection[0]);
      didSelectionChangeHappen = true;
    });
    view.querySelector('.analysis-link').click();
    assertTrue(didSelectionChangeHappen);
  });

  test('sleepingSlice', function() {
    var m = createBasicModel();

    var cpu = m.kernel.cpus[1];
    var binderSlice = cpu.slices[0];
    assertEquals('Binder_1', binderSlice.title);
    var launcherSlice = cpu.slices[1];
    assertEquals('Android.launcher', launcherSlice.title);


    var thread = m.findAllThreadsNamed('Binder_1')[0];

    var view = new tracing.analysis.ThreadTimeSliceView();
    view.modelEvent = thread.timeSlices[1];
    this.addHTMLOutput(view);

    // Clicking the analysis link should focus the Android.launcher slice
    var didSelectionChangeHappen = false;
    view.addEventListener('requestSelectionChange', function(e) {
      assertEquals(1, e.selection.length);
      assertEquals(launcherSlice, e.selection[0]);
      didSelectionChangeHappen = true;
    });
    view.querySelector('.analysis-link').click();
    assertTrue(didSelectionChangeHappen);
  });

});
