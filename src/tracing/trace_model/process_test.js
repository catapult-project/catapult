// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('tracing.trace_model.process');

'use strict';

base.unittest.testSuite('tracing.trace_model.process', function() {
  test('getOrCreateCounter', function() {
    var process = new tracing.trace_model.Process(7);
    var ctrBar = process.getOrCreateCounter('foo', 'bar');
    var ctrBar2 = process.getOrCreateCounter('foo', 'bar');
    assertEquals(ctrBar2, ctrBar);
  });

  test('shiftTimestampsForward', function() {
    var process = new tracing.trace_model.Process(7);
    var ctr = process.getOrCreateCounter('foo', 'bar');
    var thread = process.getOrCreateThread(1);

    var shiftCount = 0;
    thread.shiftTimestampsForward = function(ts) {
      if (ts == 0.32)
        shiftCount++;
    };
    ctr.shiftTimestampsForward = function(ts) {
      if (ts == 0.32)
        shiftCount++;
    };
    process.shiftTimestampsForward(0.32);
    assertEquals(2, shiftCount);
  });
});
