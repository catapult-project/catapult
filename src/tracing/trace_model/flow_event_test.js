// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.trace_model.flow_event');

base.unittest.testSuite('tracing.trace_model.flow_event', function() {
  test('isFlowEnd', function() {
    var f = new tracing.trace_model.FlowEvent('cat', 1, 'title', 1, 1, {});
    var f2 = new tracing.trace_model.FlowEvent('cat', 1, 'title', 1, 1, {});

    assertTrue(f.isFlowEnd());

    f.nextEvent = f2;

    assertFalse(f.isFlowEnd());
    assertTrue(f2.isFlowEnd());
  });

  test('isFlowStart', function() {
    var f = new tracing.trace_model.FlowEvent('cat', 1, 'title', 1, 1, {});
    var f2 = new tracing.trace_model.FlowEvent('cat', 1, 'title', 1, 1, {});

    assertTrue(f.isFlowStart());

    f.prevEvent = f2;

    assertFalse(f.isFlowStart());
    assertTrue(f2.isFlowStart());
  });

  test('nextEvent', function() {
    var f = new tracing.trace_model.FlowEvent('cat', 1, 'title', 1, 1, {});
    var f2 = new tracing.trace_model.FlowEvent('cat', 1, 'title', 1, 1, {});
    f.nextEvent = f2;

    assertEquals(f2, f.nextEvent);
    assertUndefined(f2.nextEvent);
  });

  test('prevEvent', function() {
    var f = new tracing.trace_model.FlowEvent('cat', 1, 'title', 1, 1, {});
    var f2 = new tracing.trace_model.FlowEvent('cat', 1, 'title', 1, 1, {});
    f.prevEvent = f2;

    assertEquals(f2, f.prevEvent);
    assertUndefined(f2.prevEvent);
  });
});
