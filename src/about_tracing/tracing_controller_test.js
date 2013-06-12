// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

base.require('tracing.test_utils');
base.require('about_tracing.tracing_controller');

'use strict';

base.unittest.testSuite('about_tracing.tracing_controller', function() {
  test('loadTraceFileCompleteWithJSONfiles', function() {
    var callbackFired = false;

    var traceEventData = '[{"a":1, "b":2}]';

    var tc = new about_tracing.TracingController(undefined);
    tc.addEventListener('loadTraceFileComplete', function(event) {
      callbackFired = true;
    });
    tc.onLoadTraceFileComplete(traceEventData);

    assertTrue(callbackFired);
    assertEquals(traceEventData, tc.traceEventData);
  });

  test('loadTraceFileCompleteWithNonJSONfiles', function() {
    var callbackFired = false;

    var tc = new about_tracing.TracingController(undefined);
    tc.addEventListener('loadTraceFileComplete', function(event) {
      callbackFired = true;
    });
    tc.onLoadTraceFileComplete('<DOCTYPE>');

    assertEquals('<DOCTYPE>', tc.traceEventData);
    assertTrue(callbackFired);
  });
});
