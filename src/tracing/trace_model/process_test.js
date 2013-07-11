// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('tracing.trace_model');
base.require('tracing.trace_model.process');

base.unittest.testSuite('tracing.trace_model.process', function() {
  test('getOrCreateCounter', function() {
    var model = new tracing.TraceModel();
    var process = new tracing.trace_model.Process(model, 7);
    var ctrBar = process.getOrCreateCounter('foo', 'bar');
    var ctrBar2 = process.getOrCreateCounter('foo', 'bar');
    assertEquals(ctrBar2, ctrBar);
  });

  test('shiftTimestampsForward', function() {
    var model = new tracing.TraceModel();
    var process = new tracing.trace_model.Process(model, 7);
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

  test('compareOnPID', function() {
    var model = new tracing.TraceModel();
    var p1 = new tracing.trace_model.Process(model, 1);
    p1.name = 'Renderer';

    var model = new tracing.TraceModel();
    var p2 = new tracing.trace_model.Process(model, 2);
    p2.name = 'Renderer';

    assertTrue(p1.compareTo(p2) < 0);
  });

  test('compareOnSortIndex', function() {
    var model = new tracing.TraceModel();
    var p1 = new tracing.trace_model.Process(model, 1);
    p1.name = 'Renderer';
    p1.sortIndex = 1;

    var p2 = new tracing.trace_model.Process(model, 2);
    p2.name = 'Renderer';

    assertTrue(p1.compareTo(p2) > 0);
  });

  test('compareOnName', function() {
    var model = new tracing.TraceModel();
    var p1 = new tracing.trace_model.Process(model, 1);
    p1.name = 'Browser';

    var p2 = new tracing.trace_model.Process(model, 2);
    p2.name = 'Renderer';

    assertTrue(p1.compareTo(p2) < 0);
  });

  test('compareOnLabels', function() {
    var model = new tracing.TraceModel();
    var p1 = new tracing.trace_model.Process(model, 1);
    p1.name = 'Renderer';
    p1.labels = ['a'];

    var p2 = new tracing.trace_model.Process(model, 2);
    p2.name = 'Renderer';
    p2.labels = ['b'];

    assertTrue(p1.compareTo(p2) < 0);
  });

});
