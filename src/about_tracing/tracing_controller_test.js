// Copyright (c) 2013 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

base.require('tracing.test_utils');
base.require('about_tracing.tracing_controller');

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

  function SendStub() {
    this.sends = [];
  }
  SendStub.prototype = {
    reset: function() {
      this.sends = [];
    },

    send: function(msg, args) {
      this.sends.push({
        msg: msg,
        args: args
      });
    },

    get numSends() {
      return this.sends.length;
    },

    getMessage: function(i) {
      return this.sends[i].msg;
    },

    getArgs: function(i) {
      return this.sends[i].args;
    }
  };

  test('saveTraceFile', function() {
    var sendStub = new SendStub();
    var tc = new about_tracing.TracingController(sendStub.send.bind(sendStub));
    tc.traceEventData_ = JSON.stringify([1, 2, 3]);
    assertEquals(1, sendStub.numSends);
    assertEquals('tracingControllerInitialized', sendStub.getMessage(0));
    sendStub.reset();

    tc.beginSaveTraceFile();

    assertEquals(1, sendStub.numSends);
    assertEquals('saveTraceFile', sendStub.getMessage(0));
    var savedDataString = sendStub.getArgs(0)[0];
    var savedData = JSON.parse(savedDataString);
    assertArrayEquals([1, 2, 3], savedData.traceEvents);
  });
});
