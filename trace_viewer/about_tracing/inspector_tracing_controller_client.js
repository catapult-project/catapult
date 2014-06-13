// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';
tvcm.require('tvcm.promise');
tvcm.require('about_tracing.tracing_controller_client');

tvcm.exportTo('about_tracing', function() {
  /**
   * Controls tracing using the inspector's FrontendAgentHost APIs.
   *
   * @constructor
   */
  function InspectorTracingControllerClient() {
  }

  InspectorTracingControllerClient.prototype = {
    __proto__: about_tracing.TracingControllerClient.prototype,

    beginMonitoring: function(monitoringOptions) {
    },

    endMonitoring: function() {
    },

    captureMonitoring: function() {
    },

    getMonitoringStatus: function() {
    },

    getCategories: function() {
    },

    beginRecording: function(recordingOptions) {
    },

    beginGetBufferPercentFull: function() {
    },

    endRecording: function() {
    }
  };

  return {
    InspectorTracingControllerClient: InspectorTracingControllerClient
  };
});
