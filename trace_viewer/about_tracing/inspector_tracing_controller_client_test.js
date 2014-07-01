// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.require('about_tracing.inspector_tracing_controller_client');

tvcm.unittest.testSuite('about_tracing.inspector_tracing_controller_client_test', function() { // @suppress longLineCheck
  test('beginRecording_sendCategoriesAndOptions', function() {
    var controller = new about_tracing.InspectorTracingControllerClient();
    controller.conn_ = new (function() {
      this.req = function(method, params) {
        var msg = JSON.stringify({
          id: 1,
          method: method,
          params: params
        });
        return new (function() {
          this.msg = msg;
          this.then = function(m1, m2) {
            return this;
          };
        })();
      };
      this.setNotificationListener = function(method, listener) {
      };
    })();
    var recordingOptions = {
      categoryFilter: JSON.stringify(['a', 'b', 'c']),
      useSystemTracing: false,
      useContinuousTracing: true,
      useSampling: true
    };

    var result = JSON.parse(controller.beginRecording(recordingOptions).msg);
    assertEquals(result.params.categories, JSON.stringify(['a', 'b', 'c']));
    var options = result.params.options.split(',');
    var contFlag = false;
    var sampleFlag = false;
    for (var s in options) {
      if (options[s] === 'record-continuously') contFlag = true;
      else if (options[s] === 'enable-sampling') sampleFlag = true;
      else assertEquals(options[s], '');
    }
    assertTrue(contFlag);
    assertTrue(sampleFlag);
  });
});
