// Copyright (c) 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

'use strict';

tvcm.exportTo('about_tracing', function() {
  /**
   * Communicates with content/browser/tracing_controller_impl.cc
   *
   * @constructor
   */
  function TracingControllerClient() {
  }

  TracingControllerClient.prototype = {
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
    TracingControllerClient: TracingControllerClient
  };
});
