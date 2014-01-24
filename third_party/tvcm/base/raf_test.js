// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('base.raf');

base.unittest.testSuite('base.raf', function() {
  var fakeNow = undefined;
  function withFakeWindowPerformanceNow(func) {
    var oldNow = window.performance.now;
    try {
      window.performance.now = function() { return fakeNow; };
      func();
    } finally {
      window.performance.now = oldNow;
    }
  }

  test('runIdleTaskWhileIdle', function() {
    withFakeWindowPerformanceNow(function() {
      base.forcePendingRAFTasksToRun(100000);  // Clear current RAF task queue.

      var rafRan = false;
      base.requestAnimationFrame(function() {
        rafRan = true;
      });
      var idleRan = false;
      base.requestIdleCallback(function() {
        idleRan = true;
      });
      fakeNow = 0;
      base.forcePendingRAFTasksToRun(fakeNow);
      assertFalse(idleRan);
      assertTrue(rafRan);
      base.forcePendingRAFTasksToRun(fakeNow);
      assertTrue(idleRan);
    });
  });

  test('twoShortIdleCallbacks', function() {
    withFakeWindowPerformanceNow(function() {
      base.forcePendingRAFTasksToRun(100000);  // Clear current RAF task queue.

      var idle1Ran = false;
      var idle2Ran = false;
      base.requestIdleCallback(function() {
        fakeNow += 1;
        idle1Ran = true;
      });
      base.requestIdleCallback(function() {
        fakeNow += 1;
        idle2Ran = true;
      });
      fakeNow = 0;
      base.forcePendingRAFTasksToRun(fakeNow);
      assertTrue(idle1Ran);
      assertTrue(idle2Ran);
    });
  });


  test('oneLongOneShortIdleCallback', function() {
    withFakeWindowPerformanceNow(function() {
      base.forcePendingRAFTasksToRun(100000);  // Clear current RAF task queue.

      var idle1Ran = false;
      var idle2Ran = false;
      base.requestIdleCallback(function() {
        fakeNow += 100;
        idle1Ran = true;
      });
      base.requestIdleCallback(function() {
        fakeNow += 1;
        idle2Ran = true;
      });
      fakeNow = 0;
      base.forcePendingRAFTasksToRun(fakeNow);
      assertTrue(idle1Ran);
      assertFalse(idle2Ran);

      // Reset idle1Ran to verify that it dosn't run again.
      idle1Ran = false;

      // Now run. idle2 should now run.
      base.forcePendingRAFTasksToRun(fakeNow);
      assertFalse(idle1Ran);
      assertTrue(idle2Ran);
    });
  });

  test('buggyPerformanceNowDoesNotBlockIdleTasks', function() {
    withFakeWindowPerformanceNow(function() {
      base.forcePendingRAFTasksToRun();  // Clear current RAF task queue.

      var idle1Ran = false;
      var idle2Ran = false;
      base.requestIdleCallback(function() {
        fakeNow += 100;
        idle1Ran = true;
      });
      base.requestIdleCallback(function() {
        fakeNow += 1;
        idle2Ran = true;
      });
      fakeNow = 10000;
      base.forcePendingRAFTasksToRun(0);
      assertTrue(idle1Ran);
      assertFalse(idle2Ran);

      // Reset idle1Ran to verify that it dosn't run again.
      idle1Ran = false;

      // Now run. idle2 should now run.
      base.forcePendingRAFTasksToRun(0);
      assertFalse(idle1Ran);
      assertTrue(idle2Ran);
    });
  });

});
