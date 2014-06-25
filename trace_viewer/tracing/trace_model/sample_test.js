// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('tracing.test_utils');
tvcm.require('tracing.trace_model');

tvcm.unittest.testSuite('tracing.trace_model.sample_test', function() {
  var Sample = tracing.trace_model.Sample;
  var StackFrame = tracing.trace_model.StackFrame;
  var Thread = tracing.trace_model.Thread;

  test('sampleStackTrace', function() {
    var thread = new Thread({}, 1);

    var fABC = tracing.test_utils.newStackTrace('cat', ['a', 'b', 'c']);

    var s = new Sample(undefined, thread, 'instructions_retired',
                       10, fABC, 10);
    var stackTrace = s.stackTrace;
    var stackTraceNames = stackTrace.map(function(f) { return f.title; });
    assertArrayEquals(
        ['a', 'b', 'c'],
        stackTraceNames);
  });

});
